from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import random
from datetime import date, time, datetime
from django.utils import timezone
from decimal import Decimal

from .forms import RegisterForm, DepositForm, WithdrawalForm, BankDetailsForm
from .models import PlatformSettings, CustomUser, Level, UserLevel, BankDetails, Deposit, Withdrawal, Task, PlatformBankDetails, Roulette, RouletteSettings

# --- FUNÇÃO HOME ---
def home(request):
    if request.user.is_authenticated:
        return redirect('menu')
    else:
        return redirect('cadastro')

# --- FUNÇÃO MENU ---
@login_required
def menu(request):
    user = request.user
    active_level = UserLevel.objects.filter(user=user, is_active=True).first()
    approved_deposit_total = Deposit.objects.filter(user=user, is_approved=True).aggregate(Sum('amount'))['amount__sum'] or 0
    today = date.today()
    daily_income = Task.objects.filter(user=user, completed_at__date=today).aggregate(Sum('earnings'))['earnings__sum'] or 0
    total_withdrawals = Withdrawal.objects.filter(user=user, status='Aprovado').aggregate(Sum('amount'))['amount__sum'] or 0

    try:
        platform_settings = PlatformSettings.objects.first()
        whatsapp_link = platform_settings.whatsapp_link
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'

    context = {
        'user': user,
        'active_level': active_level,
        'approved_deposit_total': approved_deposit_total,
        'daily_income': daily_income,
        'total_withdrawals': total_withdrawals,
        'whatsapp_link': whatsapp_link,
    }
    return render(request, 'menu.html', context)

# --- CADASTRO (REMOVIDO 1000 KZ) ---
def cadastro(request):
    invite_code_from_url = request.GET.get('invite', None)
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            
            # SALDO INICIAL DEFINIDO COMO 0 CONFORME PEDIDO
            user.available_balance = 0 
            
            invited_by_code = form.cleaned_data.get('invited_by_code')
            if invited_by_code:
                try:
                    invited_by_user = CustomUser.objects.get(invite_code=invited_by_code)
                    user.invited_by = invited_by_user
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Código de convite inválido.')
                    return render(request, 'cadastro.html', {'form': form})
            
            user.save()
            login(request, user)
            messages.success(request, 'Cadastro realizado com sucesso!')
            return redirect('menu')
    else:
        form = RegisterForm(initial={'invited_by_code': invite_code_from_url}) if invite_code_from_url else RegisterForm()
    
    try:
        whatsapp_link = PlatformSettings.objects.first().whatsapp_link
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'
    return render(request, 'cadastro.html', {'form': form, 'whatsapp_link': whatsapp_link})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('menu')
    else:
        form = AuthenticationForm()
    try:
        whatsapp_link = PlatformSettings.objects.first().whatsapp_link
    except (PlatformSettings.DoesNotExist, AttributeError):
        whatsapp_link = '#'
    return render(request, 'login.html', {'form': form, 'whatsapp_link': whatsapp_link})

@login_required
def user_logout(request):
    logout(request)
    return redirect('menu')

# --- DEPÓSITO ---
@login_required
def deposito(request):
    platform_bank_details = PlatformBankDetails.objects.all()
    deposit_instruction = PlatformSettings.objects.first().deposit_instruction if PlatformSettings.objects.first() else 'Instruções de depósito não disponíveis.'
    level_deposits = Level.objects.all().values_list('deposit_value', flat=True).distinct().order_by('deposit_value')
    level_deposits_list = [str(d) for d in level_deposits] 

    if request.method == 'POST':
        form = DepositForm(request.POST, request.FILES)
        if form.is_valid():
            deposit = form.save(commit=False)
            deposit.user = request.user
            deposit.save()
            return render(request, 'deposito.html', {
                'platform_bank_details': platform_bank_details,
                'deposit_instruction': deposit_instruction,
                'level_deposits_list': level_deposits_list,
                'deposit_success': True 
            })
        else:
            messages.error(request, 'Erro ao enviar o depósito.')
    
    form = DepositForm()
    context = {
        'platform_bank_details': platform_bank_details,
        'deposit_instruction': deposit_instruction,
        'form': form,
        'level_deposits_list': level_deposits_list,
        'deposit_success': False,
    }
    return render(request, 'deposito.html', context)

@login_required
def saque(request):
    # Configurações de Regras
    MIN_WITHDRAWAL_AMOUNT = 1500  
    START_TIME = time(9, 0, 0)
    END_TIME = time(17, 0, 0)
    TAXA_PERCENTUAL = Decimal('0.10')  # 10% de desconto
    
    # Dados de suporte
    withdrawal_records = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    has_bank_details = BankDetails.objects.filter(user=request.user).exists()
    
    # Lógica de Tempo e Data
    agora_full = timezone.localtime(timezone.now())
    now_time = agora_full.time()
    today_date = agora_full.date()
    dia_semana = agora_full.weekday()
    
    # Verificações de permissão
    is_working_day = dia_semana < 6  # Segunda a Sábado
    is_within_hours = START_TIME <= now_time <= END_TIME
    
    # Verifica se já sacou hoje
    withdrawals_today_count = Withdrawal.objects.filter(
        user=request.user, 
        created_at__date=today_date
    ).exclude(status='Cancelado').count()
    
    can_withdraw_today = (withdrawals_today_count == 0)

    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            # 1. Validações
            if not is_working_day:
                messages.error(request, 'Levantamentos não são permitidos aos Domingos.')
            elif not is_within_hours:
                messages.error(request, 'Fora do horário de saque (09:00 às 17:00).')
            elif not can_withdraw_today:
                messages.error(request, 'Você já realizou um levantamento hoje. Limite de 1 por dia.')
            elif not has_bank_details:
                messages.error(request, 'Adicione suas coordenadas bancárias no perfil.')
            elif amount < MIN_WITHDRAWAL_AMOUNT:
                messages.error(request, f'O valor mínimo para saque é de {MIN_WITHDRAWAL_AMOUNT} KZ.')
            elif request.user.available_balance < amount:
                messages.error(request, 'Saldo insuficiente para realizar esta operação.')
            
            else:
                # 2. LÓGICA DE EXECUÇÃO (Cálculo da Taxa)
                taxa_valor = amount * TAXA_PERCENTUAL
                valor_liquido = amount - taxa_valor
                
                # 3. CRIAÇÃO DO REGISTRO (Salvando valor bruto, taxa e líquido)
                Withdrawal.objects.create(
                    user=request.user, 
                    amount=amount,        # Valor total (ex: 3000)
                    fee=taxa_valor,       # Taxa (ex: 300)
                    net_amount=valor_liquido, # Valor a pagar (ex: 2700)
                    status='Pending'
                )
                
                # 4. DEDUÇÃO DO SALDO
                request.user.available_balance -= amount
                request.user.save()
                
                messages.success(request, f'Saque de {amount} KZ solicitado! Você receberá {valor_liquido} KZ após a taxa.')
                return redirect('saque')
    else:
        form = WithdrawalForm()

    context = {
        'form': form,
        'has_bank_details': has_bank_details,
        'is_time_to_withdraw': is_within_hours and is_working_day,
        'can_withdraw_today': can_withdraw_today,
        'MIN_WITHDRAWAL_AMOUNT': MIN_WITHDRAWAL_AMOUNT,
    }
    return render(request, 'saque.html', context)
    
# --- TAREFA ---
@login_required
def tarefa(request):
    user = request.user
    active_level = UserLevel.objects.filter(user=user, is_active=True).first()
    has_active_level = active_level is not None
    today = date.today()
    tasks_completed_today = Task.objects.filter(user=user, completed_at__date=today).count()
    
    context = {
        'has_active_level': has_active_level,
        'active_level': active_level,
        'tasks_completed_today': tasks_completed_today,
        'max_tasks': 1,
    }
    return render(request, 'tarefa.html', context)

@login_required
@require_POST
def process_task(request):
    user = request.user
    
    try:
        # 1. Busca o vínculo de nível ativo
        active_user_level = UserLevel.objects.filter(user=user, is_active=True).select_related('level').first()

        if not active_user_level:
            return JsonResponse({'success': False, 'message': 'Você não possui um nível VIP ativo.'})

        # 2. Verifica se a tarefa já foi feita hoje (evita duplicidade)
        today = timezone.localdate()
        if Task.objects.filter(user=user, completed_at__date=today).exists():
            return JsonResponse({'success': False, 'message': 'Limite diário de tarefas alcançado.'})

        # 3. Pega o valor do ganho (USANDO O NOME CORRETO DO SEU MODELS: daily_gain)
        task_earnings = Decimal(str(active_user_level.level.daily_gain))

        # 4. Registra a tarefa no banco de dados (Para aparecer no Admin)
        Task.objects.create(
            user=user, 
            earnings=task_earnings
            # completed_at é auto_now_add, então não precisa passar manualmente
        ) 
        
        # 5. Adiciona o valor ao saldo do usuário que realizou a tarefa
        user.available_balance += task_earnings
        user.save()

        # 6. Distribuição de Subsídios para a Rede (A, B, C)
        # Nível A (100 KZ)
        p1 = user.invited_by
        if p1:
            p1.available_balance += Decimal('100.00')
            p1.subsidy_balance += Decimal('100.00')
            p1.save()

            # Nível B (30 KZ)
            p2 = p1.invited_by
            if p2:
                p2.available_balance += Decimal('15.00')
                p2.subsidy_balance += Decimal('15.00')
                p2.save()

                # Nível C (10 KZ)
                p3 = p2.invited_by
                if p3:
                    p3.available_balance += Decimal('10.00')
                    p3.subsidy_balance += Decimal('10.00')
                    p3.save()

        return JsonResponse({
            'success': True, 
            'message': f'Tarefa concluída! {task_earnings} KZ foram adicionados ao seu saldo.'
        })

    except Exception as e:
        # Se der qualquer erro, o JSON evita a "Conexão Interrompida" e mostra o erro real
        return JsonResponse({'success': False, 'message': f'Erro: {str(e)}'})

@login_required
def nivel(request):
    if request.method == 'POST':
        level_id = request.POST.get('level_id')
        level_to_buy = get_object_or_404(Level, id=level_id)
        val = level_to_buy.deposit_value

        user_levels = UserLevel.objects.filter(user=request.user, is_active=True).values_list('level__id', flat=True)
        if level_to_buy.id in user_levels:
            messages.error(request, 'Você já possui este nível.')
            return redirect('nivel')

        if request.user.available_balance >= val:
            request.user.available_balance -= val
            UserLevel.objects.create(user=request.user, level=level_to_buy, is_active=True)
            request.user.level_active = True
            request.user.save()

            # Nível A (15%)
            p1 = request.user.invited_by
            if p1 and UserLevel.objects.filter(user=p1, is_active=True).exists():
                com1 = val * Decimal('0.12')
                p1.available_balance += com1
                p1.subsidy_balance += com1
                p1.save()

                # Nível B (3%)
                p2 = p1.invited_by
                if p2 and UserLevel.objects.filter(user=p2, is_active=True).exists():
                    com2 = val * Decimal('0.02')
                    p2.available_balance += com2
                    p2.subsidy_balance += com2
                    p2.save()

                    # Nível C (1%)
                    p3 = p2.invited_by
                    if p3 and UserLevel.objects.filter(user=p3, is_active=True).exists():
                        com3 = val * Decimal('0.01')
                        p3.available_balance += com3
                        p3.subsidy_balance += com3
                        p3.save()

            messages.success(request, f'Nível {level_to_buy.name} ativado!')
        else:
            messages.error(request, 'Saldo insuficiente.')
        return redirect('nivel')
    
    context = {
        'levels': Level.objects.all().order_by('deposit_value'),
        'user_levels': UserLevel.objects.filter(user=request.user, is_active=True).values_list('level__id', flat=True),
    }
    return render(request, 'nivel.html', context)

@login_required
def equipa(request):
    user = request.user
    # Otimizado: prefetch_related busca os níveis de uma vez só
    level_a = CustomUser.objects.filter(invited_by=user).prefetch_related('userlevel_set__level')
    level_b = CustomUser.objects.filter(invited_by__in=level_a)
    level_c = CustomUser.objects.filter(invited_by__in=level_b)

    # Membros do Nível A com investimento ativo
    level_a_active_count = level_a.filter(userlevel__is_active=True).distinct().count()
    
    # Cálculo dos SEM INVESTIMENTO (Inativos) do Nível A
    level_a_inactive_count = level_a.count() - level_a_active_count

    context = {
        'team_count': level_a.count() + level_b.count() + level_c.count(),
        'invite_link': request.build_absolute_uri(reverse('cadastro')) + f'?invite={user.invite_code}',
        'subsidy_balance': user.subsidy_balance,
        'level_a_members': level_a,
        'level_a_count': level_a.count(),
        'level_a_inactive': level_a_inactive_count,
        'level_b_count': level_b.count(),
        'level_c_count': level_c.count(),
    }
    return render(request, 'equipa.html', context)

# --- ROLETA ---
@login_required
def roleta(request):
    user = request.user
    roulette_settings = RouletteSettings.objects.first()
    prizes_list = [p.strip() for p in roulette_settings.prizes.split(',')] if roulette_settings and roulette_settings.prizes else ['0', '500', '1000', '0', '5000', '200', '0', '10000']
    recent_winners = Roulette.objects.filter(is_approved=True).order_by('-spin_date')[:10]
    context = {'roulette_spins': user.roulette_spins, 'prizes_list': prizes_list, 'recent_winners': recent_winners}
    return render(request, 'roleta.html', context)

@login_required
@require_POST
def spin_roulette(request):
    user = request.user
    if not user.roulette_spins or user.roulette_spins <= 0:
        return JsonResponse({'success': False, 'message': 'Sem giros.'})

    roulette_settings = RouletteSettings.objects.first()
    prizes_raw = [p.strip() for p in roulette_settings.prizes.split(',')] if roulette_settings and roulette_settings.prizes else ['0', '500', '1000', '0', '5000', '200', '0', '10000']
    weighted_pool = []
    for p in prizes_raw:
        val = Decimal(p)
        if val == 0: weighted_pool.extend([p] * 10)
        elif val <= 500: weighted_pool.extend([p] * 5)
        else: weighted_pool.append(p)

    winning_prize_str = random.choice(weighted_pool)
    prize_amount = Decimal(winning_prize_str)
    user.roulette_spins -= 1
    user.subsidy_balance += prize_amount
    user.available_balance += prize_amount
    user.save()
    Roulette.objects.create(user=user, prize=prize_amount, is_approved=True)

    return JsonResponse({'success': True, 'prize': winning_prize_str, 'remaining_spins': user.roulette_spins})

@login_required
def sobre(request):
    platform_settings = PlatformSettings.objects.first()
    history_text = platform_settings.history_text if platform_settings else 'Informação indisponível.'
    return render(request, 'sobre.html', {'history_text': history_text})

@login_required
def perfil(request):
    bank_details, _ = BankDetails.objects.get_or_create(user=request.user)
    withdrawal_records = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        if 'update_bank' in request.POST:
            form = BankDetailsForm(request.POST, instance=bank_details)
            if form.is_valid():
                form.save()
                messages.success(request, 'Banco atualizado.')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Senha alterada.')
        return redirect('perfil')
    
    context = {
        'form': BankDetailsForm(instance=bank_details),
        'password_form': PasswordChangeForm(request.user),
        'user_levels': UserLevel.objects.filter(user=request.user, is_active=True),
        'withdrawal_records': withdrawal_records,
    }
    return render(request, 'perfil.html', context)

@login_required
def renda(request):
    user = request.user
    active_level = UserLevel.objects.filter(user=user, is_active=True).first()
    approved_deposit_total = Deposit.objects.filter(user=user, is_approved=True).aggregate(Sum('amount'))['amount__sum'] or 0
    today = date.today()
    daily_income = Task.objects.filter(user=user, completed_at__date=today).aggregate(Sum('earnings'))['earnings__sum'] or 0
    total_withdrawals = Withdrawal.objects.filter(user=user, status='Aprovado').aggregate(Sum('amount'))['amount__sum'] or 0
    total_income = (Task.objects.filter(user=user).aggregate(Sum('earnings'))['earnings__sum'] or 0) + user.subsidy_balance
    
    context = {
        'user': user,
        'active_level': active_level,
        'approved_deposit_total': approved_deposit_total,
        'daily_income': daily_income,
        'total_withdrawals': total_withdrawals,
        'total_income': total_income,
    }
    return render(request, 'renda.html', context)
    