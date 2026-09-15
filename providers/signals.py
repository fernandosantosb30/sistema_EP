from datetime import timedelta
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

@receiver(user_logged_in, dispatch_uid='providers.absolute_login_expiry')
def fixar_expiracao(sender, request, user, **kwargs):
    if request is not None:
        request.session.set_expiry(timezone.now() + timedelta(hours=24))
