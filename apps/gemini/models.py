from uuid import uuid4 as uuid
from django.db import models
from django.contrib.auth import get_user_model # Para vincular a usuarios si aplica
from django_extensions.db.models import TimeStampedModel
# Create your models here.

User = get_user_model() # Obtiene el modelo de usuario activo en tu proyecto

class BaseModel(TimeStampedModel):
    id = models.UUIDField(
        primary_key=True,
        editable=False,
        default=uuid
    )

    class Meta:
        abstract = True


class Conversation(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,  # Si el usuario se elimina, las conversaciones persisten
        null=True,
        blank=True,
        help_text="El usuario asociado a esta conversación (si aplica)."
    )
    topic = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Tema principal o categorización de la conversación (detectado o asignado manualmente)."
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Campo JSON para metadata adicional y flexible (e.g., source, platform, user_agent)."
    )

    def __str__(self):
        return f"Conversation {self.id} with {self.user.username if self.user else 'Guest'}"

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ['-created']  # Ordenar por las conversaciones más recientes

class Message(BaseModel):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,  # Si se elimina la conversación, sus mensajes también
        related_name='messages',  # Permite acceder a los mensajes desde una conversación: conversation.messages.all()
        help_text="La conversación a la que pertenece este mensaje."
    )
    sender_type = models.CharField(
        max_length=50,
        choices=[('user', 'User'), ('model', 'Model')],
        help_text="Tipo de emisor del mensaje (user o ai)."
    )
    text_content = models.TextField(help_text="El contenido textual del mensaje.")
    token_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Número de tokens utilizados por este mensaje (útil para costos/límites de API)."
    )
    model_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Nombre del modelo de IA utilizado para generar la respuesta (e.g., gemini-1.5-flash)."
    )
    # Puede ser útil para modelos con múltiples 'parts' o para almacenar la estructura raw de la respuesta
    raw_response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos JSON brutos de la respuesta de la API de IA (si es una respuesta de IA)."
    )
    # Evaluación del mensaje (e.g., thumbs up/down, relevancia)
    feedback_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(1, 'Good'), (0, 'Bad')],  # O más granular, e.g., 1-5
        help_text="Calificación o feedback del usuario sobre la calidad de la respuesta."
    )
    feedback_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notas o comentarios adicionales sobre el feedback."
    )

    # Podrías añadir un campo para el propósito/función del mensaje
    # function_call = models.JSONField(...) si usas function calling de Gemini

    def __str__(self):
        return f"Message {self.id} from {self.sender_type} in Conversation {self.conversation.id}"

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created']  # Ordenar cronológicamente dentro de la conversación
