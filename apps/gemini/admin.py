from django.contrib import admin
from .models import Message, Conversation
# Register your models here.


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id"]

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation"]