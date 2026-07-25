from django.contrib import admin
from .models import Lead, LeadActivity, LeadTask, LeadDocument, Client

admin.site.register(Lead)
admin.site.register(LeadActivity)
admin.site.register(LeadTask)
admin.site.register(LeadDocument)
admin.site.register(Client)