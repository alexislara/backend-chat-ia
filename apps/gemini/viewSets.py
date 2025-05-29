import os
from math import hypot

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action  # Para acciones personalizadas
from rest_framework.validators import ValidationError

from google import genai

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer

User = get_user_model()

class GeminiIA:
    @staticmethod
    def gemini_model(history):
        chat = None
        try:
            IAModel = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            chat = IAModel.chats.create(model="gemini-2.0-flash", history=history)
        except AttributeError:
            print("Advertencia: settings.GEMINI_API_KEY no configurado. Las llamadas a Gemini fallarán.")

        return chat


class ConversationViewSet(
    mixins.CreateModelMixin,  # Permite crear una nueva conversación (POST /conversations/)
    mixins.RetrieveModelMixin,  # Permite obtener una conversación por ID (GET /conversations/{id}/)
    mixins.ListModelMixin,  # Permite listar todas las conversaciones (GET /conversations/)
    mixins.UpdateModelMixin,  # Permite actualizar una conversación (PUT/PATCH /conversations/{id}/)
    viewsets.GenericViewSet,  # La base para ViewSets que usan Mixins
):
    """
    ViewSet para las operaciones CRUD de las conversaciones.
    Permite crear, listar, recuperar y actualizar conversaciones.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer

    # permission_classes = [IsAuthenticated] # Considera añadir permisos en producción

    # Opcional: Personalizar la creación para asignar al usuario autenticado
    def perform_create(self, serializer):
        serializer.save(user=User.objects.first())


class MessageViewSet(
    mixins.CreateModelMixin,  # Permite crear un nuevo mensaje (POST /messages/)
    mixins.RetrieveModelMixin,  # Permite obtener un mensaje por ID (GET /messages/{id}/)
    mixins.ListModelMixin,  # Permite listar todos los mensajes (GET /messages/)
    viewsets.GenericViewSet,
    GeminiIA    # Base para ViewSets con Mixins
):
    """
    ViewSet para los mensajes. Principalmente usado para listar y como base
    para la acción personalizada `generate_ai_response`.
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    @action(detail=False, methods=['POST'], url_path='generate-ai-response')
    def generate_ai_response(self, request):
        user_prompt_text = request.data.get('text')
        conversation_id = request.data.get('conversation_id')
        user = User.objects.first()

        if not user_prompt_text:
            return Response({"detail": "The 'text' field is required."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if conversation_id:
                try:
                    conversation = get_object_or_404(Conversation, id=conversation_id)

                    if user and conversation.user and conversation.user != user:
                        return Response({"detail": "Conversation does not belong to the current user."},
                                        status=status.HTTP_403_FORBIDDEN)
                except Exception as e:
                    return Response({"detail": f"Invalid conversation ID or error: {e}"},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                conversation = Conversation.objects.create(user=user)

            current_conversation_id = str(conversation.id)

            history = []
            all_previous_messages = Message.objects.filter(conversation=conversation).order_by('created')

            for msg in all_previous_messages:
                # Cada mensaje en el historial debe tener un rol y el contenido
                history.append({
                    "role": msg.sender_type, # 'user' o 'ai'
                    "parts": [{"text": msg.text_content}]
                })

            # --- Lógica del Prompt del Sistema (si es el primer mensaje o para cada llamada) ---
            system_instruction = """Eres un asistente virtual experto en tecnologías de desarrollo web modernas,
            especialmente React, Next.js y Django REST Framework.
            Tu objetivo es proporcionar respuestas precisas y concisas sobre estos temas.
            Si la pregunta no está directamente relacionada con desarrollo web o tecnologías web (ej. preguntas sobre historia, medicina, física),
            debes responder amablemente que solo puedes ayudar con temas de desarrollo web.
            Siempre mantén un tono profesional y servicial.
            """

            if not history:
                contents_to_send = [
                    {"role": "user", "parts": [{"text": f"{system_instruction}\n\n{user_prompt_text}"}]}
                ]
            else:
                contents_to_send = history + [{"role": "user", "parts": [{"text": user_prompt_text}]}]

            _gemini_model = self.gemini_model(contents_to_send)

            Message.objects.create(
                conversation=conversation,
                sender_type='user',
                text_content=user_prompt_text,
            )

            ai_text = "Lo siento, el servicio de IA no está disponible."
            gemini_token_count = None
            raw_response_data = {"error": "AI model not initialized."}

            if _gemini_model:
                try:
                    gemini_response = _gemini_model.send_message(user_prompt_text)

                    print(gemini_response)
                    ai_text = gemini_response.text

                    if hasattr(gemini_response, 'usage_metadata'):
                        gemini_token_count = gemini_response.usage_metadata.prompt_token_count + gemini_response.usage_metadata.candidates_token_count
                    raw_response_data = {}
                    if hasattr(gemini_response, 'candidates'):
                        raw_response_data['candidates'] = [c for c in gemini_response.to_json_dict().get("candidates", {})]
                    if hasattr(gemini_response, 'usage_metadata'):
                        raw_response_data['usage_metadata'] = gemini_response.to_json_dict().get("usage_metadata", {})
                    print(raw_response_data)
                except Exception as e:
                    ai_text = f"Lo siento, hubo un error al procesar tu solicitud con la IA: {e}"
                    raise ValidationError({"error": str(e)})

            ai_message = Message.objects.create(
                conversation=conversation,
                sender_type='model',
                text_content=ai_text,
                token_count=gemini_token_count,
                model_name=_gemini_model._model if _gemini_model else "N/A",
                raw_response_data=raw_response_data
            )

        serializer = self.get_serializer(ai_message)
        response_data = serializer.data
        response_data['conversation_id'] = current_conversation_id

        return Response(response_data, status=status.HTTP_201_CREATED)