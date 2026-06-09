from django.contrib import admin

from .models import ClientDownload, Node, Setting, Source, SubscriptionUser, UserNode


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "enabled", "last_synced_at")
    search_fields = ("name", "url")
    list_filter = ("enabled",)


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "enabled", "source_label", "updated_at")
    search_fields = ("name", "type", "source_name")
    list_filter = ("enabled", "type")


class UserNodeInline(admin.TabularInline):
    model = UserNode
    extra = 0


@admin.register(SubscriptionUser)
class SubscriptionUserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "enabled", "created_at")
    search_fields = ("username", "remark")
    list_filter = ("enabled",)
    inlines = [UserNodeInline]


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key",)
    search_fields = ("key",)


@admin.register(ClientDownload)
class ClientDownloadAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "platform_code", "platform", "version", "enabled", "sort_order", "file_name", "updated_at")
    search_fields = ("name", "platform", "version", "download_url")
    list_filter = ("enabled", "platform_code", "platform")
