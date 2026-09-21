from django.conf import settings


def presentation(request):
    # Apenas valores públicos de apresentação; nunca expõe credenciais ao template.
    return {'public_brand': {'name': settings.SITE_NAME, 'partner_label': settings.PARTNER_LABEL}}
