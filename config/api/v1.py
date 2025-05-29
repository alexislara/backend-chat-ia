from rest_framework.routers import DefaultRouter
from apps.gemini.viewSets import ConversationViewSet,MessageViewSet

router = DefaultRouter()

router.register(prefix=r"conversation", viewset=ConversationViewSet, basename="conversations")
router.register(prefix=r"message", viewset=MessageViewSet, basename="messages")

urlpatterns = router.urls