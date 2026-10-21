from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
import yaml
from dotenv import load_dotenv
from flask import Flask, Request, Response, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, case, create_engine, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, scoped_session, sessionmaker


load_dotenv()


def utcnow():
    """Naive UTC timestamp (the database stores naive UTC datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class LargeFormRequest(Request):
    max_form_memory_size = int(os.getenv("MAX_FORM_MEMORY_SIZE", str(16 * 1024 * 1024)))


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nodes = relationship("Node", back_populates="source")


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), default="手动添加", nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id"), nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    source = relationship("Source", back_populates="nodes")
    users = relationship("UserNode", back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("source_id", "config_hash", name="uq_source_config_hash"),)

    @property
    def source_label(self):
        return self.source.name if self.source else (self.source_name or "手动添加")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_sub_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sub_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_sub_ua: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    sub_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    nodes = relationship("UserNode", back_populates="user", cascade="all, delete-orphan")


class UserNode(Base):
    __tablename__ = "user_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=False)

    user = relationship("User", back_populates="nodes")
    node = relationship("Node", back_populates="users")

    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_user_node"),)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5
DEFAULT_PASSWORDS = {"", "change-me", "admin", "password", "123456"}


def create_app():
    app = Flask(__name__)
    app.request_class = LargeFormRequest
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    app.config["MAX_FORM_MEMORY_SIZE"] = int(os.getenv("MAX_FORM_MEMORY_SIZE", str(16 * 1024 * 1024)))
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.getenv("SESSION_DAYS", "7")))

    db_url = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    ensure_schema(engine)
    ensure_default_settings(engine)
    db_session = scoped_session(sessionmaker(bind=engine, autoflush=False, future=True))
    login_failures = defaultdict(list)
    tz_offset = timedelta(hours=float(os.getenv("TZ_OFFSET_HOURS", "8")))

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    def db():
        return db_session()

    def login_required(view):
        def wrapped(*args, **kwargs):
            if not session.get("admin_logged_in"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        wrapped.__name__ = view.__name__
        return wrapped

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(24)
        return session["csrf_token"]

    @app.before_request
    def check_csrf():
        if request.method != "POST":
            return None
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent, expected):
            flash("页面已过期，请重新操作", "error")
            return redirect(request.referrer or url_for("index"))
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return gzip_response(response)

    @app.template_filter("dt")
    def format_datetime(value, fmt="%Y-%m-%d %H:%M"):
        if not value:
            return "-"
        return (value + tz_offset).strftime(fmt)

    @app.template_filter("fromjson")
    def from_json(value):
        try:
            return json.loads(value or "{}")
        except ValueError:
            return {}

    @app.template_filter("ago")
    def format_ago(value):
        if not value:
            return "从未"
        seconds = int((utcnow() - value).total_seconds())
        if seconds < 60:
            return "刚刚"
        if seconds < 3600:
            return f"{seconds // 60} 分钟前"
        if seconds < 86400:
            return f"{seconds // 3600} 小时前"
        if seconds < 86400 * 30:
            return f"{seconds // 86400} 天前"
        return format_datetime(value, "%Y-%m-%d")

    @app.context_processor
    def inject_globals():
        return {
            "now": utcnow(),
            "csrf_token": csrf_token,
            "csrf_field": lambda: Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'),
            "weak_password": os.getenv("ADMIN_PASSWORD", "change-me") in DEFAULT_PASSWORDS,
            "next_url": safe_next(),
        }

    def client_ip():
        # Only trust X-Real-IP from a local reverse proxy; otherwise anyone could spoof it to dodge login rate limits.
        remote = request.remote_addr or "-"
        if remote in ("127.0.0.1", "::1") and request.headers.get("X-Real-IP"):
            return request.headers["X-Real-IP"].strip()
        return remote

    def safe_next():
        target = request.form.get("next") or request.args.get("next") or ""
        if target.startswith("/") and not target.startswith("//") and "\\" not in target:
            return target
        return None

    def back_to(endpoint, **values):
        return redirect(safe_next() or url_for(endpoint, **values))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("admin_logged_in"):
            return redirect(url_for("index"))
        if request.method == "POST":
            ip = client_ip()
            cutoff = time.time() - LOGIN_WINDOW_SECONDS
            login_failures[ip] = [t for t in login_failures[ip] if t > cutoff]
            if len(login_failures[ip]) >= LOGIN_MAX_FAILURES:
                flash("登录失败次数过多，请 15 分钟后再试", "error")
                return render_template("login.html"), 429
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            expected_user = os.getenv("ADMIN_USERNAME", "admin")
            expected_password = os.getenv("ADMIN_PASSWORD", "change-me")
            user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
            password_ok = hmac.compare_digest(password.encode(), expected_password.encode())
            if user_ok and password_ok:
                login_failures.pop(ip, None)
                session.clear()
                session.permanent = True
                session["admin_logged_in"] = True
                return redirect(url_for("index"))
            login_failures[ip].append(time.time())
            app.logger.warning("admin login failed from %s", ip)
            flash("用户名或密码错误", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        s = db()
        stats = {
            "sources": s.query(Source).count(),
            "nodes": s.query(Node).count(),
            "enabled_nodes": s.query(Node).filter_by(enabled=True).count(),
            "users": s.query(User).count(),
            "enabled_users": s.query(User).filter_by(enabled=True).count(),
            "source_errors": s.query(Source).filter(Source.last_error.isnot(None)).count(),
            "active_users": s.query(User).filter(User.last_sub_at >= utcnow() - timedelta(days=1)).count(),
        }
        type_counts = s.query(Node.type, func.count(Node.id)).group_by(Node.type).order_by(func.count(Node.id).desc()).all()
        source_items = s.query(Source).order_by(Source.id.desc()).all()
        node_counts = source_node_counts(s)
        recent_users = (
            s.query(User)
            .order_by(case((User.last_sub_at.is_(None), 1), else_=0), User.last_sub_at.desc(), User.id.desc())
            .limit(8)
            .all()
        )
        user_node_counts = user_enabled_node_counts(s)
        return render_template(
            "index.html",
            stats=stats,
            type_counts=type_counts,
            sources=source_items,
            node_counts=node_counts,
            recent_users=recent_users,
            user_node_counts=user_node_counts,
        )

    @app.route("/sources", methods=["GET", "POST"])
    @login_required
    def sources():
        s = db()
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            url = request.form.get("url", "").strip()
            try:
                validate_remote_template_url(url)
            except ValueError:
                flash("订阅 URL 必须是 http 或 https 地址", "error")
                return redirect(url_for("sources"))
            source = Source(name=name, url=url)
            s.add(source)
            s.commit()
            if request.form.get("sync_now"):
                run_source_sync(s, source)
            else:
                flash("订阅源已添加", "ok")
            return redirect(url_for("sources"))
        items = s.query(Source).order_by(Source.id.desc()).all()
        return render_template("sources.html", sources=items, node_counts=source_node_counts(s))

    def run_source_sync(s, source):
        try:
            result = sync_clash_source(s, source)
            source.last_synced_at = utcnow()
            source.last_error = None
            s.commit()
            message = f"「{source.name}」同步完成：新增 {result['added']}，更新 {result['updated']}"
            if result["missing"]:
                message += f"，上游已移除 {result['missing']} 个（已标记为失效）"
            flash(message, "ok")
            return True
        except Exception as exc:
            s.rollback()
            source.last_error = str(exc)
            s.commit()
            flash(f"「{source.name}」同步失败：{exc}", "error")
            return False

    @app.route("/sources/<int:source_id>/sync", methods=["POST"])
    @login_required
    def sync_source(source_id):
        s = db()
        source = s.get(Source, source_id)
        if not source:
            flash("订阅源不存在", "error")
            return redirect(url_for("sources"))
        run_source_sync(s, source)
        return back_to("sources")

    @app.route("/sources/sync-all", methods=["POST"])
    @login_required
    def sync_all_sources():
        s = db()
        items = s.query(Source).filter_by(enabled=True).order_by(Source.id.asc()).all()
        if not items:
            flash("没有已启用的订阅源", "error")
        for source in items:
            run_source_sync(s, source)
        return back_to("sources")

    @app.route("/sources/<int:source_id>/edit", methods=["POST"])
    @login_required
    def edit_source(source_id):
        s = db()
        source = s.get(Source, source_id)
        if not source:
            flash("订阅源不存在", "error")
            return redirect(url_for("sources"))
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        try:
            validate_remote_template_url(url)
        except ValueError:
            flash("订阅 URL 必须是 http 或 https 地址", "error")
            return redirect(url_for("sources"))
        source.name = name or source.name
        source.url = url
        source.enabled = bool(request.form.get("enabled"))
        s.query(Node).filter_by(source_id=source.id).update({"source_name": source.name})
        s.commit()
        flash("订阅源已更新", "ok")
        return redirect(url_for("sources"))

    @app.route("/sources/<int:source_id>/delete", methods=["POST"])
    @login_required
    def delete_source(source_id):
        s = db()
        source = s.get(Source, source_id)
        if source:
            delete_nodes = bool(request.form.get("delete_nodes"))
            node_count = s.query(Node).filter_by(source_id=source.id).count()
            if delete_nodes:
                for node in s.query(Node).filter_by(source_id=source.id).all():
                    s.delete(node)
                message = f"订阅源已删除，并删除 {node_count} 个关联节点"
            else:
                for node in s.query(Node).filter_by(source_id=source.id).all():
                    node.source_id = None
                    node.source_name = source.name
            s.delete(source)
            s.commit()
            flash(message if delete_nodes else "订阅源已删除，已导入节点会保留并保留来源名称", "ok")
        return redirect(url_for("sources"))

    @app.route("/nodes")
    @login_required
    def nodes():
        s = db()
        selected_source = request.args.get("source", "all")
        selected_status = request.args.get("status", "all")
        selected_type = request.args.get("type", "all")
        query = s.query(Node)
        if selected_source == "manual":
            query = query.filter(Node.source_id.is_(None), Node.source_name == "手动添加")
        elif selected_source.startswith("source:"):
            try:
                query = query.filter(Node.source_id == int(selected_source.split(":", 1)[1]))
            except ValueError:
                selected_source = "all"
        if selected_type != "all":
            query = query.filter(Node.type == selected_type)
        items = query.order_by(*node_ordering()).all()
        stale_ids = stale_node_ids(s)
        if selected_status == "enabled":
            items = [node for node in items if node.enabled]
        elif selected_status == "disabled":
            items = [node for node in items if not node.enabled]
        elif selected_status == "stale":
            items = [node for node in items if node.id in stale_ids]
        source_items = s.query(Source).order_by(Source.name.asc()).all()
        types = [row[0] for row in s.query(Node.type).distinct().order_by(Node.type.asc()).all()]
        usage = dict(s.query(UserNode.node_id, func.count(UserNode.id)).group_by(UserNode.node_id).all())
        return render_template(
            "nodes.html",
            nodes=items,
            sources=source_items,
            types=types,
            usage=usage,
            stale_ids=stale_ids,
            selected_source=selected_source,
            selected_status=selected_status,
            selected_type=selected_type,
            total=s.query(Node).count(),
        )

    @app.route("/nodes/new", methods=["GET", "POST"])
    @login_required
    def new_node():
        text_value = ""
        if request.method == "POST":
            text_value = request.form.get("node_text", "").strip()
            blocks = split_manual_nodes(text_value)
            added, errors = 0, []
            for index, block in enumerate(blocks, start=1):
                try:
                    config = parse_manual_node(block)
                    save_node(db(), config, raw_text=block, source=None)
                    added += 1
                except Exception as exc:
                    db().rollback()
                    errors.append(f"第 {index} 条：{exc}")
            if added:
                flash(f"已添加 {added} 个节点", "ok")
            for error in errors[:5]:
                flash(f"添加失败 · {error}", "error")
            if added and not errors:
                return redirect(url_for("nodes"))
            if not blocks:
                flash("请输入 URI 或 YAML 节点配置", "error")
        return render_template("node_form.html", node_text=text_value)

    @app.route("/nodes/<int:node_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_node(node_id):
        s = db()
        node = s.get(Node, node_id)
        if not node:
            flash("节点不存在", "error")
            return redirect(url_for("nodes"))
        editable_config = node.source_id is None
        bound_users = [link.user for link in node.users]
        if request.method == "POST":
            previous_name = node.name
            node.name = request.form["name"].strip() or previous_name
            node.tags = request.form.get("tags", "").strip() or None
            node.remark = request.form.get("remark", "").strip() or None
            node.enabled = bool(request.form.get("enabled"))
            if editable_config:
                config_text = request.form.get("config_text", "").strip()
                try:
                    config = normalize_proxy(yaml.safe_load(config_text))
                except Exception as exc:
                    flash(f"配置无效：{exc}", "error")
                    return render_template(
                        "node_edit.html",
                        node=node,
                        editable_config=editable_config,
                        config_text=config_text,
                        readonly_config=formatted_node_config(node),
                        bound_users=bound_users,
                    )
                # Whichever name the admin actually edited wins; the name field takes precedence if both changed.
                if node.name != previous_name or config["name"] == previous_name:
                    config["name"] = node.name
                node.name = config["name"]
                node.type = config["type"]
                node.config_hash = config_hash(config)
                node.config_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
                node.raw_text = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
            else:
                config = json.loads(node.config_json)
                config["name"] = node.name
                node.config_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
            s.commit()
            flash("节点已更新", "ok")
            return redirect(safe_next() or url_for("nodes"))
        return render_template(
            "node_edit.html",
            node=node,
            editable_config=editable_config,
            config_text=formatted_node_config(node),
            readonly_config=formatted_node_config(node),
            bound_users=bound_users,
        )

    @app.route("/nodes/<int:node_id>/toggle", methods=["POST"])
    @login_required
    def toggle_node(node_id):
        s = db()
        node = s.get(Node, node_id)
        if node:
            node.enabled = not node.enabled
            s.commit()
        return back_to("nodes")

    @app.route("/nodes/<int:node_id>/delete", methods=["POST"])
    @login_required
    def delete_node(node_id):
        s = db()
        node = s.get(Node, node_id)
        if node:
            s.delete(node)
            s.commit()
            flash("节点已删除", "ok")
        return back_to("nodes")

    @app.route("/nodes/bulk", methods=["POST"])
    @app.route("/nodes/bulk-delete", methods=["POST"])
    @login_required
    def bulk_delete_nodes():
        s = db()
        action = request.form.get("action", "delete")
        node_ids = {int(value) for value in request.form.getlist("node_ids") if value.isdigit()}
        if not node_ids:
            flash("请先勾选节点", "error")
            return back_to("nodes")
        items = s.query(Node).filter(Node.id.in_(node_ids)).all()
        if action == "enable":
            for node in items:
                node.enabled = True
            message = f"已启用 {len(items)} 个节点"
        elif action == "disable":
            for node in items:
                node.enabled = False
            message = f"已禁用 {len(items)} 个节点"
        else:
            for node in items:
                s.delete(node)
            message = f"已删除 {len(items)} 个节点"
        s.commit()
        flash(message, "ok")
        return back_to("nodes")

    @app.route("/users", methods=["GET", "POST"])
    @login_required
    def users():
        s = db()
        if request.method == "POST":
            user = User(
                username=request.form["username"].strip(),
                remark=request.form.get("remark", "").strip() or None,
                token=new_token(),
            )
            s.add(user)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                flash("用户名已存在", "error")
                return redirect(url_for("users"))
            flash("用户已创建，现在为 TA 绑定节点", "ok")
            return redirect(url_for("user_detail", user_id=user.id))
        items = s.query(User).order_by(User.id.desc()).all()
        for user in items:
            user.sub_url = subscription_url(user.token)
        return render_template("users.html", users=items, node_counts=user_enabled_node_counts(s))

    @app.route("/users/<int:user_id>", methods=["GET", "POST"])
    @login_required
    def user_detail(user_id):
        s = db()
        user = s.get(User, user_id)
        if not user:
            flash("用户不存在", "error")
            return redirect(url_for("users"))
        if request.method == "POST":
            user.username = request.form["username"].strip()
            user.remark = request.form.get("remark", "").strip() or None
            user.enabled = bool(request.form.get("enabled"))
            selected_ids = {int(x) for x in request.form.getlist("node_ids") if x.isdigit()}
            current_ids = {link.node_id for link in user.nodes}
            for link in list(user.nodes):
                if link.node_id not in selected_ids:
                    s.delete(link)
            for node_id in selected_ids - current_ids:
                if s.get(Node, node_id):
                    s.add(UserNode(user_id=user.id, node_id=node_id))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                flash("用户名已存在", "error")
                return redirect(url_for("user_detail", user_id=user_id))
            flash(f"用户已更新，当前绑定 {len(selected_ids)} 个节点", "ok")
            return redirect(url_for("user_detail", user_id=user.id))
        all_nodes = s.query(Node).order_by(*node_ordering()).all()
        selected = {link.node_id for link in user.nodes}
        node_groups = group_nodes_by_source(all_nodes)
        return render_template(
            "user_detail.html",
            user=user,
            node_groups=node_groups,
            selected=selected,
            stale_ids=stale_node_ids(s),
            sub_url=subscription_url(user.token),
        )

    @app.route("/users/<int:user_id>/toggle", methods=["POST"])
    @login_required
    def toggle_user(user_id):
        s = db()
        user = s.get(User, user_id)
        if user:
            user.enabled = not user.enabled
            s.commit()
            flash(f"用户「{user.username}」已{'启用' if user.enabled else '禁用'}", "ok")
        return back_to("users")

    @app.route("/users/<int:user_id>/preview")
    @login_required
    def preview_user_config(user_id):
        s = db()
        user = s.get(User, user_id)
        if not user:
            return "not found", 404
        return Response(render_subscription(s, user), mimetype="text/plain; charset=utf-8")

    @app.route("/users/<int:user_id>/reset-token", methods=["POST"])
    @login_required
    def reset_token(user_id):
        s = db()
        user = s.get(User, user_id)
        if user:
            user.token = new_token()
            s.commit()
            flash("订阅 token 已重置，旧链接已失效", "ok")
        return redirect(url_for("user_detail", user_id=user_id))

    @app.route("/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    def delete_user(user_id):
        s = db()
        user = s.get(User, user_id)
        if user:
            s.delete(user)
            s.commit()
            flash("用户已删除", "ok")
        return redirect(url_for("users"))

    @app.route("/settings/template", methods=["GET", "POST"])
    @login_required
    def template_settings():
        s = db()
        current_template = get_setting(s, "clash_template", "") or get_setting(s, "remote_template_cache", "")
        remote_url = get_setting(s, "remote_template_url", "")
        remote_updated_at = get_setting(s, "remote_template_updated_at", "")
        if request.method == "POST":
            current_template = request.form.get("template", "").strip()
            if current_template:
                try:
                    validate_template(current_template)
                except Exception as exc:
                    flash(f"模板无效：{exc}", "error")
                    return render_template_page(s, current_template, remote_url, remote_updated_at)
            set_setting(s, "clash_template", current_template)
            s.commit()
            flash("模板已保存", "ok")
            return redirect(url_for("template_settings"))
        return render_template_page(s, current_template, remote_url, remote_updated_at)

    def render_template_page(s, current_template, remote_url, remote_updated_at, sort_text=None):
        if sort_text is None:
            sort_text = get_setting(s, "node_sort_keywords", "")
        names = [node.name for node in s.query(Node).filter_by(enabled=True).order_by(*node_ordering()).all()]
        template_groups = template_proxy_groups(current_template)
        return render_template(
            "template_settings.html",
            template=current_template,
            remote_url=remote_url,
            remote_updated_at=remote_updated_at,
            sort_text=sort_text,
            node_names=names,
            group_choices=group_default_choices(template_groups),
            group_defaults=get_group_defaults(s),
        )

    @app.route("/settings/group-defaults", methods=["POST"])
    @login_required
    def group_defaults_settings():
        s = db()
        template_text = get_setting(s, "clash_template", "")
        choices = group_default_choices(template_proxy_groups(template_text))
        saved = {}
        for name, choice in zip(request.form.getlist("group_name"), request.form.getlist("group_choice")):
            allowed = {value for value, _ in choices.get(name, {}).get("options", [])}
            if choice and choice in allowed:
                saved[name] = choice
        set_setting(s, "group_defaults", json.dumps(saved, ensure_ascii=False))
        s.commit()
        flash(f"规则组默认选项已保存（自定义 {len(saved)} 个组），用户下次刷新订阅生效", "ok")
        return redirect(url_for("template_settings") + "#group-defaults")

    @app.route("/settings/node-order", methods=["POST"])
    @login_required
    def node_order_settings():
        s = db()
        sort_text = "\n".join(line.rstrip() for line in request.form.get("sort_keywords", "").strip().splitlines())
        set_setting(s, "node_sort_keywords", sort_text)
        s.commit()
        rules = parse_sort_rules(sort_text)
        flash(f"节点排序已保存（{len(rules)} 条优先级规则），用户下次刷新订阅生效" if rules else "已清空节点排序规则", "ok")
        return redirect(url_for("template_settings") + "#node-order")

    @app.route("/settings/template/fetch", methods=["POST"])
    @login_required
    def fetch_remote_template():
        s = db()
        remote_url = request.form.get("remote_url", "").strip() or get_setting(s, "remote_template_url", "")
        try:
            validate_remote_template_url(remote_url)
            config_text = fetch_template_from_url(remote_url)
            template = extract_template_from_config(config_text)
            validate_template(template)
            set_setting(s, "remote_template_url", remote_url)
            set_setting(s, "clash_template", template)
            set_setting(s, "remote_template_updated_at", utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
            s.commit()
            flash("已从远程配置提取模板", "ok")
        except Exception as exc:
            flash(f"远程配置提取失败：{exc}", "error")
        return redirect(url_for("template_settings"))

    @app.route("/settings/template/extract", methods=["POST"])
    @login_required
    def extract_template():
        s = db()
        config_text = request.form.get("config_text", "").strip()
        try:
            template = extract_template_from_config(config_text)
            validate_template(template)
            set_setting(s, "clash_template", template)
            s.commit()
            flash("已从配置文件提取模板", "ok")
        except Exception as exc:
            flash(f"提取失败：{exc}", "error")
        return redirect(url_for("template_settings"))

    @app.route("/sub/<token>")
    def subscribe(token):
        return subscription_response(db(), token, client_ip(), request.headers.get("User-Agent", ""))

    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.ico")

    return app


def sync_clash_source(session, source):
    resp = requests.get(source.url, timeout=20, headers={"User-Agent": "clash.meta/proxy-share"})
    resp.raise_for_status()
    text = decode_subscription_body(resp.content)
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("proxies"), list):
        raise ValueError("订阅不是有效的 mihomo/Clash YAML，缺少 proxies")
    upstream = []
    for item in data["proxies"]:
        if isinstance(item, dict):
            config = normalize_proxy(item)
            upstream.append((config, config_hash(config), item))
    if not upstream:
        raise ValueError("订阅中没有任何节点")
    upstream_hashes = {digest for _, digest, _ in upstream}
    existing_nodes = session.query(Node).filter_by(source_id=source.id).all()
    by_hash = {node.config_hash: node for node in existing_nodes}
    seen_ids = set()
    result = {"added": 0, "updated": 0, "missing": 0}
    for config, digest, item in upstream:
        node = by_hash.get(digest)
        if node is not None and node.id in seen_ids:
            continue
        if node is None:
            # Upstream rotated credentials / params: reuse the node with the same name so user bindings survive.
            node = next(
                (
                    n for n in existing_nodes
                    if n.id not in seen_ids and n.config_hash not in upstream_hashes and upstream_name(n) == config["name"]
                ),
                None,
            )
        raw_text = yaml.safe_dump(item, allow_unicode=True, sort_keys=False)
        if node is None:
            node = Node(
                name=config["name"],
                type=config["type"],
                raw_text=raw_text,
                config_json=json.dumps(config, ensure_ascii=False, sort_keys=True),
                config_hash=digest,
                source_name=source.name,
                source=source,
            )
            session.add(node)
            session.flush()
            by_hash[digest] = node
            result["added"] += 1
        else:
            custom_name = node.name if node.name != upstream_name(node) else None
            stored = dict(config, name=custom_name) if custom_name else config
            node.name = stored["name"]
            node.type = config["type"]
            node.raw_text = raw_text
            node.config_hash = digest
            node.config_json = json.dumps(stored, ensure_ascii=False, sort_keys=True)
            node.source_name = source.name
            node.stale = False
            node.updated_at = utcnow()
            by_hash[digest] = node
            result["updated"] += 1
        seen_ids.add(node.id)
    for node in existing_nodes:
        if node.id not in seen_ids:
            node.stale = True
            result["missing"] += 1
    session.commit()
    return result


def gzip_response(response):
    if (
        response.direct_passthrough
        or response.status_code != 200
        or "Content-Encoding" in response.headers
        or "gzip" not in request.headers.get("Accept-Encoding", "").lower()
        or not (response.mimetype.startswith("text/") or response.mimetype in {"application/javascript", "image/svg+xml"})
    ):
        return response
    data = response.get_data()
    if len(data) < 1024:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    response.vary.add("Accept-Encoding")
    return response


def upstream_name(node):
    try:
        item = yaml.safe_load(node.raw_text or "")
        if isinstance(item, dict) and item.get("name"):
            return str(item["name"])
    except yaml.YAMLError:
        pass
    return node.name


def source_node_counts(session):
    counts = defaultdict(lambda: {"total": 0, "enabled": 0, "stale": 0})
    for source_id, enabled, stale, count in (
        session.query(Node.source_id, Node.enabled, Node.stale, func.count(Node.id))
        .group_by(Node.source_id, Node.enabled, Node.stale)
        .all()
    ):
        counts[source_id]["total"] += count
        if enabled:
            counts[source_id]["enabled"] += count
        if stale:
            counts[source_id]["stale"] += count
    return counts


def user_enabled_node_counts(session):
    rows = (
        session.query(UserNode.user_id, func.count(UserNode.id))
        .join(Node, Node.id == UserNode.node_id)
        .filter(Node.enabled.is_(True))
        .group_by(UserNode.user_id)
        .all()
    )
    return dict(rows)


def stale_node_ids(session):
    return {row[0] for row in session.query(Node.id).filter(Node.stale.is_(True)).all()}


def split_manual_nodes(text):
    """Accept one YAML node, a YAML list of nodes, a `proxies:` block, or several URIs (one per line)."""
    text = (text or "").strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and all("://" in line and not line.startswith(("#", "-", "{")) for line in lines):
        return lines
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return [text]
    if isinstance(data, dict) and isinstance(data.get("proxies"), list):
        data = data["proxies"]
    if isinstance(data, list):
        return [yaml.safe_dump(item, allow_unicode=True, sort_keys=False) for item in data if isinstance(item, dict)]
    return [text]


def ensure_schema(engine):
    columns = {column["name"] for column in inspect(engine).get_columns("nodes")}
    with engine.begin() as conn:
        if "source_name" not in columns:
            conn.execute(text("ALTER TABLE nodes ADD COLUMN source_name VARCHAR(200) NOT NULL DEFAULT '手动添加'"))
        if "stale" not in columns:
            conn.execute(text("ALTER TABLE nodes ADD COLUMN stale BOOLEAN NOT NULL DEFAULT 0"))
        user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
        for name, ddl in {
            "last_sub_at": "DATETIME",
            "last_sub_ip": "VARCHAR(64)",
            "last_sub_ua": "VARCHAR(300)",
            "sub_count": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in user_columns:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
        conn.execute(text(
            """
            UPDATE nodes
            SET source_name = (
                SELECT sources.name
                FROM sources
                WHERE sources.id = nodes.source_id
            )
            WHERE source_id IS NOT NULL
              AND EXISTS (
                SELECT 1
                FROM sources
                WHERE sources.id = nodes.source_id
              )
            """
        ))


def ensure_default_settings(engine):
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT value FROM settings WHERE key = 'clash_template'")).scalar()
        if not existing:
            conn.execute(
                text("INSERT OR REPLACE INTO settings (key, value) VALUES (:key, :value)"),
                {"key": "clash_template", "value": default_template_text()},
            )


def save_node(session, config, raw_text=None, source=None):
    config = normalize_proxy(config)
    digest = config_hash(config)
    source_name = source.name if source else "手动添加"
    existing = None
    if source:
        existing = session.query(Node).filter_by(source_id=source.id, config_hash=digest).first()
    if existing:
        existing.name = config["name"]
        existing.type = config["type"]
        existing.source_name = source_name
        existing.raw_text = raw_text
        existing.config_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
        existing.updated_at = utcnow()
    else:
        node = Node(
            name=config["name"],
            type=config["type"],
            raw_text=raw_text,
            config_json=json.dumps(config, ensure_ascii=False, sort_keys=True),
            config_hash=digest,
            source_name=source_name,
            source=source,
        )
        session.add(node)
    session.commit()


def normalize_proxy(config):
    if not isinstance(config, dict):
        raise ValueError("节点配置必须是 YAML 对象")
    if not config.get("name"):
        raise ValueError("节点缺少 name")
    if not config.get("type"):
        raise ValueError("节点缺少 type")
    config = dict(config)
    config["name"] = str(config["name"])
    config["type"] = str(config["type"]).lower()
    return use_servername(config)


def use_servername(config):
    """mihomo reads the TLS server name of vless/vmess from "servername" and silently ignores "sni"."""
    if config.get("type") in {"vless", "vmess"} and "sni" in config:
        sni = config.pop("sni")
        config.setdefault("servername", sni)
    return config


def parse_manual_node(text):
    if not text:
        raise ValueError("请输入 URI 或 YAML 节点配置")
    if "://" in text and not text.lstrip().startswith("{"):
        return parse_proxy_uri(text)
    data = yaml.safe_load(text)
    return normalize_proxy(data)


def parse_proxy_uri(uri):
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme == "vmess":
        return parse_vmess(uri)
    if scheme in {"vless", "trojan", "hysteria", "hysteria2", "hy2", "tuic", "wireguard", "socks", "socks5", "http", "https"}:
        return parse_url_style_proxy(uri, scheme)
    if scheme == "ss":
        return parse_ss(uri)
    if scheme == "ssr":
        return parse_ssr(uri)
    raise ValueError(f"暂不支持的 URI 协议：{scheme}")


def parse_vmess(uri):
    payload = uri.split("://", 1)[1]
    data = json.loads(b64decode_text(payload))
    network = data.get("net")
    config = {
        "name": data.get("ps") or data.get("add") or "vmess",
        "type": "vmess",
        "server": data.get("add"),
        "port": int(data.get("port")),
        "uuid": data.get("id"),
        "alterId": int(data.get("aid") or 0),
        "cipher": data.get("scy") or data.get("cipher") or "auto",
        "tls": str(data.get("tls", "")).lower() == "tls",
    }
    if network:
        config["network"] = network
    if network == "ws":
        config["ws-opts"] = {"path": data.get("path") or "/", "headers": {"Host": data.get("host") or ""}}
    if data.get("sni"):
        config["servername"] = data["sni"]
    return normalize_proxy(clean_empty(config))


def parse_url_style_proxy(uri, scheme):
    parsed = urlparse(uri)
    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    proxy_type = {"hy2": "hysteria2", "socks5": "socks", "https": "http"}.get(scheme, scheme)
    config = {
        "name": unquote(parsed.fragment) if parsed.fragment else parsed.hostname or proxy_type,
        "type": proxy_type,
        "server": parsed.hostname,
        "port": parsed.port,
    }
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if proxy_type == "vless":
        config["uuid"] = username
        config["tls"] = query.get("security") in {"tls", "reality"} or query.get("tls") == "1"
        if query.get("security") == "reality":
            config["reality-opts"] = clean_empty({"public-key": query.get("pbk"), "short-id": query.get("sid")})
    elif proxy_type in {"trojan", "hysteria", "hysteria2", "tuic"}:
        config["password"] = username or password
    elif proxy_type == "wireguard":
        config["private-key"] = username or password
    elif proxy_type in {"socks", "http"}:
        if username:
            config["username"] = username
        if password:
            config["password"] = password
    for src, dst in {
        "type": "network",
        "encryption": "cipher",
        "sni": "sni",
        "fp": "client-fingerprint",
        "alpn": "alpn",
        "host": "host",
        "path": "path",
        "flow": "flow",
        "allowInsecure": "skip-cert-verify",
    }.items():
        if src in query:
            config[dst] = query[src]
    return normalize_proxy(clean_empty(config))


def parse_ss(uri):
    body = uri.split("://", 1)[1]
    name = "shadowsocks"
    if "#" in body:
        body, frag = body.split("#", 1)
        name = unquote(frag)
    if "@" not in body:
        decoded = b64decode_text(body)
        if "#" in decoded:
            decoded, frag = decoded.split("#", 1)
            name = unquote(frag)
        body = decoded
    auth, server = body.rsplit("@", 1)
    if ":" not in auth:
        auth = b64decode_text(auth)
    cipher, password = auth.split(":", 1)
    host, port = split_host_port(server)
    return normalize_proxy({"name": name, "type": "ss", "server": host, "port": int(port), "cipher": cipher, "password": password})


def parse_ssr(uri):
    decoded = b64decode_text(uri.split("://", 1)[1])
    parts = decoded.split("/?", 1)
    main = parts[0].split(":")
    if len(main) < 6:
        raise ValueError("SSR URI 格式不完整")
    query = {k: v[-1] for k, v in parse_qs(parts[1] if len(parts) > 1 else "").items()}
    name = b64decode_text(query.get("remarks", "")) if query.get("remarks") else main[0]
    return normalize_proxy({
        "name": name,
        "type": "ssr",
        "server": main[0],
        "port": int(main[1]),
        "cipher": main[3],
        "password": b64decode_text(main[5]),
        "obfs": main[4],
        "protocol": main[2],
    })


YamlLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
FIRST_NODE = "__PROXIES__"
FIXED_TARGETS = {"DIRECT", "REJECT", "REJECT-DROP", "PASS", "COMPATIBLE"}


def load_yaml(text):
    return yaml.load(text, Loader=YamlLoader)


def build_subscription(proxies, template_text="", group_defaults=None):
    if template_text:
        doc = load_yaml(template_text) or {}
        if not isinstance(doc, dict):
            raise ValueError("模板顶层必须是 YAML 对象")
    else:
        doc = default_subscription()
    sanitize_nameserver_policy(doc)
    proxy_names = [p["name"] for p in proxies]
    doc["proxies"] = proxies
    groups = apply_group_defaults(doc.get("proxy-groups"), group_defaults or {})
    doc["proxy-groups"] = apply_proxy_group_names(groups, proxy_names)
    if "rules" not in doc:
        doc["rules"] = ["MATCH,Proxy"]
    return doc


def default_subscription():
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": [],
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": ["__PROXIES__"]}],
        "rules": ["MATCH,Proxy"],
    }


def template_proxy_groups(template_text):
    if not template_text:
        return None
    try:
        doc = load_yaml(template_text)
    except yaml.YAMLError:
        return None
    return doc.get("proxy-groups") if isinstance(doc, dict) else None


def expand_policy_domain(key):
    """mihomo only allows the "+" wildcard in the first label; older cores silently ignored e.g. "+.bilivideo.+".

    A trailing "+" is expanded to common TLDs, any other misplaced "+" makes the entry unusable and it is dropped.
    """
    if "," in key or ":" in key.split(".", 1)[0]:
        return [key]  # multi-domain keys and geosite:/rule-set: references are left alone
    labels = key.split(".")
    if "+" not in labels[1:]:
        return [key]
    if labels[-1] == "+" and "+" not in labels[1:-1]:
        base = ".".join(labels[:-1])
        return [f"{base}.{tld}" for tld in ("com", "cn", "net")]
    return []


def sanitize_nameserver_policy(doc):
    dns = doc.get("dns")
    policy = dns.get("nameserver-policy") if isinstance(dns, dict) else None
    if not isinstance(policy, dict):
        return
    fixed = {}
    for key, value in policy.items():
        for domain in expand_policy_domain(str(key)):
            fixed.setdefault(domain, value)
    dns["nameserver-policy"] = fixed


def group_default_choices(groups):
    """Allowed default options per configurable select group, excluding choices that would create a reference cycle."""
    if not isinstance(groups, list):
        return {}
    groups = [g for g in groups if isinstance(g, dict) and g.get("name")]
    names = [str(g["name"]) for g in groups]
    refs = {str(g["name"]): [str(p) for p in (g.get("proxies") or []) if str(p) in names] for g in groups}

    def reaches(start, target):
        stack, seen = [start], set()
        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(refs.get(current, []))
        return False

    result = {}
    for group in groups:
        name = str(group["name"])
        members = [str(p) for p in (group.get("proxies") or [])] if isinstance(group.get("proxies"), list) else []
        if group.get("type") != "select" or not members or set(members) <= FIXED_TARGETS:
            continue
        options = [("DIRECT", "DIRECT 直连")]
        options += [(other, other) for other in names if other != name and not reaches(other, name)]
        options.append((FIRST_NODE, "第一个节点"))
        if "REJECT" in members:
            options.append(("REJECT", "REJECT 拒绝"))
        first = members[0]
        result[name] = {
            "options": options,
            "template_default": "第一个节点" if first == FIRST_NODE else first,
        }
    return result


def apply_group_defaults(groups, defaults):
    if not defaults or not isinstance(groups, list):
        return groups
    choices = group_default_choices(groups)
    result = []
    for group in groups:
        if not isinstance(group, dict):
            result.append(group)
            continue
        name = str(group.get("name"))
        choice = defaults.get(name)
        allowed = {value for value, _ in choices.get(name, {}).get("options", [])}
        if choice and choice in allowed:
            group = dict(group)
            members = [p for p in (group.get("proxies") or []) if p != choice]
            group["proxies"] = [choice] + members
        result.append(group)
    return result


def get_group_defaults(session):
    try:
        data = json.loads(get_setting(session, "group_defaults", "") or "{}")
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items() if v} if isinstance(data, dict) else {}


def apply_proxy_group_names(groups, proxy_names):
    if not isinstance(groups, list) or not groups:
        return [{"name": "Proxy", "type": "select", "proxies": proxy_names}]
    result = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        item = dict(group)
        item["proxies"] = expand_proxy_placeholders(item.get("proxies"), proxy_names)
        result.append(item)
    return result or [{"name": "Proxy", "type": "select", "proxies": proxy_names}]


def expand_proxy_placeholders(value, proxy_names):
    if value is None:
        return proxy_names
    if not isinstance(value, list):
        return proxy_names
    expanded = []
    for item in value:
        if item == "__PROXIES__":
            expanded.extend(proxy_names)
        else:
            expanded.append(item)
    return expanded


def validate_template(template_text):
    data = yaml.safe_load(template_text)
    if not isinstance(data, dict):
        raise ValueError("顶层必须是 YAML 对象")
    if "proxies" in data and not isinstance(data["proxies"], list):
        raise ValueError("proxies 必须是列表，或者删掉让系统自动生成")
    if "proxy-groups" in data and not isinstance(data["proxy-groups"], list):
        raise ValueError("proxy-groups 必须是列表")


def extract_template_from_config(config_text):
    if not config_text:
        raise ValueError("请粘贴完整 mihomo/Clash 配置")
    data = yaml.safe_load(config_text)
    if not isinstance(data, dict):
        raise ValueError("配置顶层必须是 YAML 对象")
    proxies = data.get("proxies") or []
    if not isinstance(proxies, list):
        raise ValueError("proxies 必须是列表")
    proxy_names = {str(proxy.get("name")) for proxy in proxies if isinstance(proxy, dict) and proxy.get("name")}
    template = dict(data)
    template.pop("proxies", None)
    groups = template.get("proxy-groups")
    if isinstance(groups, list):
        template["proxy-groups"] = [extract_proxy_group_template(group, proxy_names) for group in groups if isinstance(group, dict)]
    elif proxy_names:
        template["proxy-groups"] = [{"name": "Proxy", "type": "select", "proxies": ["__PROXIES__"]}]
    return yaml.safe_dump(template, allow_unicode=True, sort_keys=False)


def extract_proxy_group_template(group, proxy_names):
    item = dict(group)
    values = item.get("proxies")
    if not isinstance(values, list):
        item["proxies"] = ["__PROXIES__"]
        return item
    kept = []
    removed_proxy = False
    has_placeholder = False
    for value in values:
        if value == "__PROXIES__":
            has_placeholder = True
        elif str(value) in proxy_names:
            removed_proxy = True
        else:
            kept.append(value)
    if removed_proxy or has_placeholder:
        kept = ["__PROXIES__"] + [value for value in kept if value != "__PROXIES__"]
    item["proxies"] = kept
    return item


def validate_remote_template_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("远程模板 URL 必须是 http 或 https 地址")


def fetch_template_from_url(url):
    resp = requests.get(url, timeout=20, headers={"User-Agent": "proxy-share/0.1"})
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise ValueError("远程模板为空")
    return text


def default_template_text():
    return yaml.safe_dump(default_subscription(), allow_unicode=True, sort_keys=False)


def get_setting(session, key, default=""):
    setting = session.get(Setting, key)
    return setting.value if setting else default


def set_setting(session, key, value):
    setting = session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))


def group_nodes_by_source(nodes):
    groups = []
    index = {}
    for node in nodes:
        label = node.source_label
        if label not in index:
            index[label] = {"label": label, "nodes": []}
            groups.append(index[label])
        index[label]["nodes"].append(node)
    return groups


def node_ordering():
    manual_first = case((Node.source_id.is_(None), 0), else_=1)
    return manual_first, Node.source_name.asc(), Node.name.asc(), Node.id.asc()


def node_sort_key(node):
    return (
        0 if node.source_id is None else 1,
        node.source_name or "",
        node.name or "",
        node.id or 0,
    )


def formatted_node_config(node):
    return yaml.safe_dump(json.loads(node.config_json), allow_unicode=True, sort_keys=False)


def config_hash(config):
    raw = json.dumps(config, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decode_subscription_body(content):
    text = content.decode("utf-8", errors="ignore").strip()
    if text.startswith(("proxies:", "mixed-port:", "port:", "proxy-groups:")):
        return text
    try:
        decoded = b64decode_text(text)
        if "proxies:" in decoded:
            return decoded
    except Exception:
        pass
    return text


def b64decode_text(value):
    value = value.strip()
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode()).decode("utf-8")


def split_host_port(value):
    if value.startswith("["):
        host, port = value.rsplit("]:", 1)
        return host[1:], port
    return value.rsplit(":", 1)


def clean_empty(data):
    return {k: v for k, v in data.items() if v not in (None, "", {}, [])}


def unique_name(name, used):
    candidate = str(name)
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while f"{candidate} {i}" in used:
        i += 1
    final = f"{candidate} {i}"
    used.add(final)
    return final


def new_token():
    return secrets.token_urlsafe(32)


def subscription_url(token):
    base = request.host_url.rstrip("/")
    return f"{base}/sub/{token}"


def parse_sort_rules(text):
    """One priority level per line; alternatives on the same line separated by | (case-insensitive)."""
    rules = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keywords = [part.strip().lower() for part in line.split("|") if part.strip()]
        if keywords:
            rules.append(keywords)
    return rules


def sort_priority(name, rules):
    lowered = (name or "").lower()
    for index, keywords in enumerate(rules):
        if any(keyword in lowered for keyword in keywords):
            return index
    return len(rules)


def apply_sort_rules(items, rules, name_of):
    if not rules:
        return list(items)
    return sorted(items, key=lambda item: sort_priority(name_of(item), rules))


def render_subscription(session, user):
    configs = []
    used_names = set()
    nodes = sorted((link.node for link in user.nodes if link.node.enabled), key=node_sort_key)
    rules = parse_sort_rules(get_setting(session, "node_sort_keywords", ""))
    loaded = [(node, use_servername(json.loads(node.config_json))) for node in nodes]
    loaded = apply_sort_rules(loaded, rules, lambda pair: pair[1].get("name") or pair[0].name)
    for node, config in loaded:
        config["name"] = unique_name(config.get("name") or node.name, used_names)
        configs.append(config)
    template = get_setting(session, "clash_template", "")
    doc = build_subscription(configs, template, get_group_defaults(session))
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def subscription_response(session, token, ip="-", user_agent=""):
    user = session.query(User).filter_by(token=token, enabled=True).first()
    if not user:
        return "not found", 404
    body = render_subscription(session, user)
    user.last_sub_at = utcnow()
    user.last_sub_ip = (ip or "-")[:64]
    user.last_sub_ua = (user_agent or "")[:300] or None
    user.sub_count = (user.sub_count or 0) + 1
    session.commit()
    response = Response(body, mimetype="text/yaml")
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(user.username)}"
    response.headers["profile-update-interval"] = os.getenv("PROFILE_UPDATE_HOURS", "12")
    response.headers["Cache-Control"] = "no-store"
    return response


app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    if os.getenv("FLASK_DEBUG") == "1":
        app.run(host=host, port=port, debug=True)
    else:
        try:
            from waitress import serve
        except ImportError:
            app.run(host=host, port=port)
        else:
            print(f"Proxy Share listening on http://{host}:{port}", flush=True)
            serve(app, host=host, port=port, threads=int(os.getenv("THREADS", "8")), ident="proxy-share")
