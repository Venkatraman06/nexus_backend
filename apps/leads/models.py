from django.db import models
from apps.common.models import BaseModel


class Lead(BaseModel):
    class Status(models.TextChoices):
        LEAD          = "LEAD",          "Lead"
        CONTACTED     = "CONTACTED",     "Contacted"
        PROPOSAL_SENT = "PROPOSAL_SENT", "Proposal Sent"
        WON           = "WON",           "Won"
        LOST          = "LOST",          "Lost"

    class Priority(models.TextChoices):
        LOW    = "LOW",    "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH   = "HIGH",   "High"

    name                 = models.CharField(max_length=300)
    company              = models.CharField(max_length=300, blank=True, default="")
    college              = models.CharField(max_length=300, blank=True, default="")
    contact_person       = models.CharField(max_length=200)
    designation          = models.CharField(max_length=200, blank=True, default="")
    phone                = models.CharField(max_length=50, blank=True, default="")
    whatsapp             = models.CharField(max_length=50, blank=True, default="")
    email                = models.EmailField(blank=True, default="")
    location             = models.CharField(max_length=200, blank=True, default="")
    lead_source          = models.CharField(max_length=100, blank=True, default="Website")
    status               = models.CharField(max_length=20, choices=Status.choices, default=Status.LEAD)
    priority             = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    remarks              = models.TextField(blank=True, default="")
    expected_deal_value  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    training_requirement = models.TextField(blank=True, default="")
    follow_up_date       = models.DateField(null=True, blank=True)
    next_follow_up       = models.DateField(null=True, blank=True)
    last_contact_date    = models.DateField(null=True, blank=True)
    notes                = models.TextField(blank=True, default="")
    business_category = models.CharField(max_length=100, blank=True, default='')
    deal_title        = models.CharField(max_length=300, blank=True, default='')
    deal_description  = models.TextField(blank=True, default='')
    deal_amount       = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deal_date_from    = models.DateField(null=True, blank=True)
    deal_date_to      = models.DateField(null=True, blank=True)
    assigned_to       = models.CharField(max_length=100, blank=True, default='')  # legacy, can keep or drop
    assigned_to_name  = models.CharField(max_length=200, blank=True, default='')  # legacy, can keep or drop
    assigned_employees = models.ManyToManyField(
        "accounts.Employee", blank=True, related_name="assigned_leads_m2m"
    )

    class Meta:
        db_table = "crm_lead"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class LeadActivity(BaseModel):
    class ActivityType(models.TextChoices):
        CALL      = "CALL",      "Call"
        MEETING   = "MEETING",   "Meeting"
        EMAIL     = "EMAIL",     "Email"
        WHATSAPP  = "WHATSAPP",  "WhatsApp"
        NOTE      = "NOTE",      "Note"
        REMINDER  = "REMINDER",  "Reminder"

    lead           = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name="activities")
    activity_type  = models.CharField(max_length=20, choices=ActivityType.choices, default=ActivityType.CALL)
    title          = models.CharField(max_length=300, null=True, blank=True)
    description    = models.TextField(blank=True, default="")
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_lead_activity"
        ordering = ["-created_at"]

    @property
    def lead_name(self):
        return self.lead.name if self.lead else None


class LeadTask(BaseModel):
    lead      = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tasks")
    title     = models.CharField(max_length=300)
    due_date  = models.DateField()
    completed = models.BooleanField(default=False)

    class Meta:
        db_table = "crm_lead_task"
        ordering = ["-created_at"]

    @property
    def lead_name(self):
        return self.lead.name


class LeadDocument(BaseModel):
    lead        = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="documents")
    name        = models.CharField(max_length=300)
    doc_type    = models.CharField(max_length=100, default="Requirement")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_lead_document"
        ordering = ["-uploaded_at"]

    @property
    def lead_name(self):
        return self.lead.name


class Client(BaseModel):
    class BusinessCategory(models.TextChoices):
        TRAINING   = "TRAINING",   "Training"
        CONSULTING = "CONSULTING", "Consulting"
        SALES      = "SALES",      "Sales"

    name               = models.CharField(max_length=300)
    company            = models.CharField(max_length=300, blank=True, default="")
    college            = models.CharField(max_length=300, blank=True, default="")
    contact_person     = models.CharField(max_length=200, blank=True, default="")
    phone              = models.CharField(max_length=50, blank=True, default="")
    whatsapp           = models.CharField(max_length=50, blank=True, default="")
    email              = models.EmailField(blank=True, default="")
    relationship_score = models.IntegerField(default=80)
    status             = models.CharField(max_length=50, default="Active")
    notes              = models.TextField(blank=True, default="")

    business_category  = models.CharField(max_length=20, choices=BusinessCategory.choices, blank=True, default="")
    deal_title          = models.CharField(max_length=300, blank=True, default="")
    deal_description     = models.TextField(blank=True, default="")
    deal_amount          = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deal_date_from        = models.DateField(null=True, blank=True)
    deal_date_to           = models.DateField(null=True, blank=True)
    assigned_to          = models.ForeignKey(
        "accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_clients"
    )
    assigned_employees = models.ManyToManyField(
        "accounts.Employee", blank=True, related_name="assigned_clients_m2m"
    )

    class Meta:
        db_table = "crm_client"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ClientChatRoom(BaseModel):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name="chat_room")
    name = models.CharField(max_length=300, blank=True, default="")
    participants = models.ManyToManyField("accounts.Employee", related_name="client_chat_rooms")

    class Meta:
        db_table = "crm_client_chat_room"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or f"Chat: {self.client.name}"


class ClientChatMessage(BaseModel):
    room = models.ForeignKey(ClientChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey("accounts.Employee", on_delete=models.SET_NULL, null=True, related_name="+")
    text = models.TextField()

    class Meta:
        db_table = "crm_client_chat_message"
        ordering = ["created_at"]