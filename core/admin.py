from django.contrib import admin
from django.utils.safestring import mark_safe # Importação necessária para renderizar HTML no Admin
from .models import (
    CustomUser, PlatformSettings, Level, BankDetails, Deposit, 
    Withdrawal, Task, Roulette, RouletteSettings, UserLevel, PlatformBankDetails
)

# ---

# Registrando os modelos com classes ModelAdmin personalizadas

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'available_balance', 'subsidy_balance', 'is_staff', 'is_active', 'date_joined', 'roulette_spins')
    search_fields = ('phone_number', 'invite_code')
    list_filter = ('is_staff', 'is_active', 'level_active')

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'whatsapp_link', 'history_text', 'deposit_instruction', 'withdrawal_instruction')
    search_fields = ('whatsapp_link',)

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'deposit_value', 'daily_gain', 'monthly_gain', 'cycle_days')
    search_fields = ('name',)

@admin.register(BankDetails)
class BankDetailsAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'account_holder_name')
    search_fields = ('user__phone_number', 'bank_name', 'account_holder_name')

@admin.register(PlatformBankDetails)
class PlatformBankDetailsAdmin(admin.ModelAdmin):
    list_display = ('bank_name', 'account_holder_name')
    search_fields = ('bank_name', 'account_holder_name')

@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'is_approved', 'created_at', 'proof_link') 
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)
    readonly_fields = ('current_proof_display',)

    def save_model(self, request, obj, form, change):
        # Verifica se o depósito está sendo marcado como aprovado e se ele ainda não estava aprovado antes
        if obj.is_approved:
            original_obj = Deposit.objects.filter(pk=obj.pk).first()
            if not original_obj or not original_obj.is_approved:
                # Soma o valor ao saldo do usuário
                user = obj.user
                user.available_balance += obj.amount
                user.save()
        
        super().save_model(request, obj, form, change)

    def proof_link(self, obj):
        if obj.proof_of_payment:
            return mark_safe(f'<a href="{obj.proof_of_payment.url}" target="_blank">Ver Comprovativo</a>')
        return "Nenhum"
    proof_link.short_description = 'Comprovativo'

    def current_proof_display(self, obj):
        if obj.proof_of_payment:
            return mark_safe(f'''
                <a href="{obj.proof_of_payment.url}" target="_blank">Ver Imagem em Tamanho Real</a><br/>
                <img src="{obj.proof_of_payment.url}" style="max-width:300px; height:auto; margin-top: 10px;" />
            ''')
        return "Nenhum Comprovativo Carregado"
    current_proof_display.short_description = 'Comprovativo Atual'

@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    # Adicionamos as funções que buscam os dados bancários na lista
    list_display = ('user', 'amount', 'net_amount', 'get_iban', 'get_bank_name', 'get_holder', 'status', 'created_at')
    search_fields = ('user__phone_number',)
    list_filter = ('status',)
    list_editable = ('status',)

    # Métodos para buscar dados do modelo BankDetails do usuário
    def get_iban(self, obj):
        details = BankDetails.objects.filter(user=obj.user).first()
        return details.IBAN if details else "Não cadastrado"
    get_iban.short_description = 'IBAN Cliente'

    def get_bank_name(self, obj):
        details = BankDetails.objects.filter(user=obj.user).first()
        return details.bank_name if details else "N/A"
    get_bank_name.short_description = 'Banco'

    def get_holder(self, obj):
        details = BankDetails.objects.filter(user=obj.user).first()
        return details.account_holder_name if details else "N/A"
    get_holder.short_description = 'Titular'

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'earnings', 'completed_at')
    search_fields = ('user__phone_number',)

@admin.register(Roulette)
class RouletteAdmin(admin.ModelAdmin):
    list_display = ('user', 'prize', 'is_approved', 'spin_date')
    search_fields = ('user__phone_number',)
    list_filter = ('is_approved',)

@admin.register(RouletteSettings)
class RouletteSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'prizes')

@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'purchase_date', 'is_active')
    search_fields = ('user__phone_number', 'level__name')
    list_filter = ('is_active',)

# ---
