from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from config.logging_utils import log_event
from django.contrib.auth.decorators import login_required
from .models import Vehicle, FuelEntry, MaintenanceEntry, OtherExpense, VehicleImage
from .forms import VehicleForm, GasolineFuelForm, ElectricFuelForm, MaintenanceEntryForm, OtherExpenseForm, MultipleImageUploadForm
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def record_down_payment(vehicle):
    """Record down payment as an expense when vehicle is created/edited"""
    # Check if down payment exists and is valid
    if not vehicle.down_payment:
        return False

    try:
        down_payment_amount = float(vehicle.down_payment)
        if down_payment_amount <= 0:
            return False
    except (ValueError, TypeError):
        return False

    # Check if down payment already exists
    existing = vehicle.other_expenses.filter(
        expense_type='vehicle_payment',
        notes__iexact='down payment'
    ).first()

    if existing:
        # Update existing down payment if amount changed
        if float(existing.cost) != down_payment_amount:
            existing.cost = down_payment_amount
            existing.save()
            return True
        return False

    # Use purchase date or today
    payment_date = vehicle.purchased_date if vehicle.purchased_date else date.today()

    # Create down payment expense
    OtherExpense.objects.create(
        vehicle=vehicle,
        expense_type='vehicle_payment',
        date=payment_date,
        cost=vehicle.down_payment,
        notes='Down payment'
    )
    return True


def generate_loan_payments(vehicle):
    """Auto-generate missing loan payment entries if auto-payment is enabled"""
    if not vehicle.loan_auto_payment or not all([
        vehicle.loan_start_date,
        vehicle.loan_payment_day,
        vehicle.loan_term_months
    ]):
        return 0

    monthly_payment = vehicle.get_monthly_payment()
    if not monthly_payment:
        return 0

    created_count = 0
    current_date = date.today()

    # Calculate loan end date
    loan_end_date = vehicle.loan_start_date + relativedelta(months=vehicle.loan_term_months)

    # Don't create payments beyond today or loan end
    max_date = min(current_date, loan_end_date)

    # Start from loan start date
    payment_date = vehicle.loan_start_date

    # Adjust to the correct day of month
    if payment_date.day != vehicle.loan_payment_day:
        # Move to the payment day in the same month or next month
        try:
            payment_date = payment_date.replace(day=vehicle.loan_payment_day)
        except ValueError:
            # Day doesn't exist in this month (e.g., 31st in February)
            # Move to last day of month
            next_month = payment_date.replace(day=1) + relativedelta(months=1)
            payment_date = next_month - timedelta(days=1)

    while payment_date <= max_date:
        # Check if payment already exists for this month
        month_start = payment_date.replace(day=1)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

        existing_payment = vehicle.other_expenses.filter(
            expense_type='vehicle_payment',
            notes__icontains='loan payment',
            date__gte=month_start,
            date__lte=month_end
        ).first()

        if not existing_payment:
            # Create the payment
            OtherExpense.objects.create(
                vehicle=vehicle,
                expense_type='vehicle_payment',
                date=payment_date,
                cost=monthly_payment,
                notes=f'Auto-generated loan payment'
            )
            created_count += 1

        # Move to next month's payment date
        try:
            next_month = payment_date + relativedelta(months=1)
            # Ensure we're on the correct payment day
            if next_month.day != vehicle.loan_payment_day:
                try:
                    payment_date = next_month.replace(day=vehicle.loan_payment_day)
                except ValueError:
                    # Day doesn't exist in this month
                    next_next_month = next_month.replace(day=1) + relativedelta(months=1)
                    payment_date = next_next_month - timedelta(days=1)
            else:
                payment_date = next_month
        except:
            break

    return created_count


def generate_lease_payments(vehicle):
    """Auto-generate missing lease payment entries if auto-payment is enabled"""
    if not vehicle.lease_auto_payment or not all([
        vehicle.lease_start_date,
        vehicle.lease_payment_day,
        vehicle.lease_term_months,
        vehicle.lease_payment_amount
    ]):
        return 0

    created_count = 0
    current_date = date.today()

    # Calculate lease end date
    lease_end_date = vehicle.lease_start_date + relativedelta(months=vehicle.lease_term_months)

    # Don't create payments beyond today or lease end
    max_date = min(current_date, lease_end_date)

    # Start from lease start date
    payment_date = vehicle.lease_start_date

    # Adjust to the correct day of month
    if payment_date.day != vehicle.lease_payment_day:
        # Move to the payment day in the same month or next month
        try:
            payment_date = payment_date.replace(day=vehicle.lease_payment_day)
        except ValueError:
            # Day doesn't exist in this month (e.g., 31st in February)
            # Move to last day of month
            next_month = payment_date.replace(day=1) + relativedelta(months=1)
            payment_date = next_month - timedelta(days=1)

    while payment_date <= max_date:
        # Check if payment already exists for this month
        month_start = payment_date.replace(day=1)
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

        existing_payment = vehicle.other_expenses.filter(
            expense_type='vehicle_payment',
            notes__icontains='lease payment',
            date__gte=month_start,
            date__lte=month_end
        ).first()

        if not existing_payment:
            # Create the payment
            OtherExpense.objects.create(
                vehicle=vehicle,
                expense_type='vehicle_payment',
                date=payment_date,
                cost=vehicle.lease_payment_amount,
                notes=f'Auto-generated lease payment'
            )
            created_count += 1

        # Move to next month's payment date
        try:
            next_month = payment_date + relativedelta(months=1)
            # Ensure we're on the correct payment day
            if next_month.day != vehicle.lease_payment_day:
                try:
                    payment_date = next_month.replace(day=vehicle.lease_payment_day)
                except ValueError:
                    # Day doesn't exist in this month
                    next_next_month = next_month.replace(day=1) + relativedelta(months=1)
                    payment_date = next_next_month - timedelta(days=1)
            else:
                payment_date = next_month
        except:
            break

    return created_count


@login_required
def home(request):
    active_vehicles = Vehicle.objects.filter(
        user=request.user,
        sold_date__isnull=True
    )
    log_event(
        request=request,
        event="Home view was accessed in jautolog",
        level="DEBUG",
        active_vehicle_count=active_vehicles.count()
    )
    return render(request, "autolog/home.html", {
        'vehicles': active_vehicles,
    })


@login_required
def vehicle_list(request):
    hide_sold = request.GET.get('hide_sold', 'false') == 'true'
    vehicles = Vehicle.objects.filter(user=request.user)

    if hide_sold:
        vehicles = vehicles.filter(sold_date__isnull=True)

    log_event(
        request=request,
        event="Vehicle list viewed",
        level="DEBUG",
        hide_sold=hide_sold,
        vehicle_count=vehicles.count()
    )
    return render(request, "autolog/vehicle_list.html", {
        'vehicles': vehicles,
        'hide_sold': hide_sold,
    })


@login_required
def vehicle_comparison(request):
    """Compare statistics across all vehicles"""
    from django.db.models import Sum, Avg

    vehicles = Vehicle.objects.filter(user=request.user)

    # Get sorting parameters
    sort_by = request.GET.get('sort', 'days_owned')  # Default to days_owned for mobile compatibility
    sort_dir = request.GET.get('dir', 'desc')  # 'asc' or 'desc'

    # Calculate statistics for each vehicle
    vehicle_stats_list = []

    for vehicle in vehicles:
        # Skip vehicles without purchase date or lease start date
        start_date = vehicle.purchased_date or vehicle.lease_start_date
        if not start_date:
            continue

        # Calculate days owned/leased
        end_date = vehicle.sold_date if vehicle.is_sold else date.today()
        days_owned = (end_date - start_date).days
        if days_owned == 0:
            days_owned = 1

        # Calculate miles driven
        miles_driven = 0
        start_odometer = vehicle.purchased_odometer

        if vehicle.is_sold and vehicle.sold_odometer:
            if start_odometer:
                miles_driven = vehicle.sold_odometer - start_odometer
            else:
                miles_driven = vehicle.sold_odometer
        elif start_odometer:
            latest_fuel = vehicle.fuel_entries.order_by('-odometer').first()
            latest_maintenance = vehicle.maintenance_entries.order_by('-odometer').first()

            latest_odometer = start_odometer
            if latest_fuel and latest_fuel.odometer > latest_odometer:
                latest_odometer = latest_fuel.odometer
            if latest_maintenance and latest_maintenance.odometer > latest_odometer:
                latest_odometer = latest_maintenance.odometer

            miles_driven = latest_odometer - start_odometer
        else:
            # No start odometer - use latest odometer reading
            latest_fuel = vehicle.fuel_entries.order_by('-odometer').first()
            latest_maintenance = vehicle.maintenance_entries.order_by('-odometer').first()

            if latest_fuel:
                miles_driven = latest_fuel.odometer
            if latest_maintenance and latest_maintenance.odometer > miles_driven:
                miles_driven = latest_maintenance.odometer

        # Calculate costs
        total_fuel = vehicle.fuel_entries.aggregate(total=Sum('cost'))['total'] or 0
        total_maintenance = vehicle.maintenance_entries.aggregate(total=Sum('cost'))['total'] or 0
        total_insurance = vehicle.other_expenses.filter(expense_type='insurance').aggregate(total=Sum('cost'))['total'] or 0
        total_registration = vehicle.other_expenses.filter(expense_type='registration').aggregate(total=Sum('cost'))['total'] or 0

        # Get vehicle cost (depreciation + all payments made)
        vehicle_cost = vehicle.get_vehicle_cost()

        total_cost = vehicle_cost + float(total_fuel) + float(total_maintenance) + float(total_insurance) + float(total_registration)

        # Per-day and per-mile calculations
        total_cost_per_day = total_cost / days_owned if days_owned > 0 else 0
        vehicle_cost_per_day = vehicle_cost / days_owned if days_owned > 0 else 0
        cost_per_mile = total_cost / miles_driven if miles_driven > 0 else 0

        # Average MPG (or MPGe for electric vehicles)
        if vehicle.fuel_type == 'electric':
            avg_mpg = vehicle.fuel_entries.aggregate(avg=Avg('mpge'))['avg'] or 0
        else:
            avg_mpg = vehicle.fuel_entries.aggregate(avg=Avg('mpg'))['avg'] or 0

        vehicle_stats_list.append({
            'vehicle': vehicle,
            'days_owned': days_owned,
            'miles_driven': miles_driven,
            'vehicle_cost': round(vehicle_cost, 2),
            'total_fuel': round(float(total_fuel), 2),
            'total_maintenance': round(float(total_maintenance), 2),
            'total_insurance': round(float(total_insurance), 2),
            'total_registration': round(float(total_registration), 2),
            'total_cost': round(total_cost, 2),
            'total_cost_per_day': round(total_cost_per_day, 2),
            'vehicle_cost_per_day': round(vehicle_cost_per_day, 2),
            'cost_per_mile': round(cost_per_mile, 2),
            'avg_mpg': round(float(avg_mpg), 2) if avg_mpg else 0,
        })

    # Sort the list
    sort_key_map = {
        'name': lambda x: str(x['vehicle']),
        'days_owned': lambda x: x['days_owned'],
        'miles_driven': lambda x: x['miles_driven'],
        'total_cost': lambda x: x['total_cost'],
        'total_cost_per_day': lambda x: x['total_cost_per_day'],
        'vehicle_cost_per_day': lambda x: x['vehicle_cost_per_day'],
        'cost_per_mile': lambda x: x['cost_per_mile'],
        'avg_mpg': lambda x: x['avg_mpg'],
        'vehicle_cost': lambda x: x['vehicle_cost'],
        'total_fuel': lambda x: x['total_fuel'],
        'total_maintenance': lambda x: x['total_maintenance'],
    }

    if sort_by in sort_key_map:
        reverse_sort = (sort_dir == 'desc')
        vehicle_stats_list.sort(key=sort_key_map[sort_by], reverse=reverse_sort)

    # Calculate min/max for highlighting
    if vehicle_stats_list:
        stats_keys = ['days_owned', 'miles_driven', 'total_cost', 'total_cost_per_day',
                      'vehicle_cost_per_day', 'cost_per_mile', 'avg_mpg', 'vehicle_cost',
                      'total_fuel', 'total_maintenance']

        min_max = {}
        for key in stats_keys:
            values = [v[key] for v in vehicle_stats_list if v[key] > 0]
            if values:
                min_max[f'{key}_min'] = min(values)
                min_max[f'{key}_max'] = max(values)
    else:
        min_max = {}

    log_event(
        request=request,
        event="Vehicle comparison viewed",
        level="DEBUG",
        vehicle_count=len(vehicle_stats_list),
        sort_by=sort_by
    )

    return render(request, "autolog/vehicle_comparison.html", {
        'vehicle_stats_list': vehicle_stats_list,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'min_max': min_max,
    })


@login_required
def lifetime_expense_report(request):
    """Display lifetime expense report aggregated by year across all vehicles"""
    from django.db.models import Sum
    from django.db.models.functions import ExtractYear
    import calendar

    vehicles = Vehicle.objects.filter(user=request.user)

    # Get sorting parameters
    sort_by = request.GET.get('sort', 'year')
    sort_dir = request.GET.get('dir', 'desc')

    # Build a dictionary to hold year statistics
    year_data = {}

    # Calculate vehicle count per year (fractional based on days owned)
    for vehicle in vehicles:
        start_date = vehicle.purchased_date or vehicle.lease_start_date
        if not start_date:
            continue

        end_date = vehicle.sold_date if vehicle.is_sold else date.today()

        # Iterate through each year the vehicle was owned
        current_year = start_date.year
        end_year = end_date.year

        while current_year <= end_year:
            # Determine the start and end dates for this year
            year_start = date(current_year, 1, 1)
            year_end = date(current_year, 12, 31)

            # Calculate overlap
            overlap_start = max(start_date, year_start)
            overlap_end = min(end_date, year_end)

            # Calculate days owned in this year
            days_in_year = (overlap_end - overlap_start).days + 1

            # Calculate total days in this year (handle leap years)
            total_days_in_year = 366 if calendar.isleap(current_year) else 365

            # Calculate fractional vehicle count
            vehicle_fraction = days_in_year / total_days_in_year

            # Add to year data
            if current_year not in year_data:
                year_data[current_year] = {'year': current_year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
            year_data[current_year]['vehicle_count'] += vehicle_fraction

            current_year += 1

    # Aggregate fuel expenses by year
    fuel_by_year = FuelEntry.objects.filter(
        vehicle__user=request.user
    ).annotate(
        year=ExtractYear('date')
    ).values('year').annotate(
        total=Sum('cost')
    )

    for entry in fuel_by_year:
        year = entry['year']
        if year not in year_data:
            year_data[year] = {'year': year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
        year_data[year]['fuel'] = float(entry['total'] or 0)

    # Aggregate maintenance expenses by year (all categories combined)
    maintenance_by_year = MaintenanceEntry.objects.filter(
        vehicle__user=request.user
    ).annotate(
        year=ExtractYear('date')
    ).values('year').annotate(
        total=Sum('cost')
    )

    for entry in maintenance_by_year:
        year = entry['year']
        if year not in year_data:
            year_data[year] = {'year': year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
        year_data[year]['maintenance'] = float(entry['total'] or 0)

    # Aggregate insurance expenses by year
    insurance_by_year = OtherExpense.objects.filter(
        vehicle__user=request.user,
        expense_type='insurance'
    ).annotate(
        year=ExtractYear('date')
    ).values('year').annotate(
        total=Sum('cost')
    )

    for entry in insurance_by_year:
        year = entry['year']
        if year not in year_data:
            year_data[year] = {'year': year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
        year_data[year]['insurance'] = float(entry['total'] or 0)

    # Aggregate registration expenses by year
    registration_by_year = OtherExpense.objects.filter(
        vehicle__user=request.user,
        expense_type='registration'
    ).annotate(
        year=ExtractYear('date')
    ).values('year').annotate(
        total=Sum('cost')
    )

    for entry in registration_by_year:
        year = entry['year']
        if year not in year_data:
            year_data[year] = {'year': year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
        year_data[year]['registration'] = float(entry['total'] or 0)

    # Aggregate vehicle payments by year
    payments_by_year = OtherExpense.objects.filter(
        vehicle__user=request.user,
        expense_type='vehicle_payment'
    ).annotate(
        year=ExtractYear('date')
    ).values('year').annotate(
        total=Sum('cost')
    )

    for entry in payments_by_year:
        year = entry['year']
        if year not in year_data:
            year_data[year] = {'year': year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
        year_data[year]['vehicle_cost'] = float(entry['total'] or 0)

    # Add depreciation to purchase year for each vehicle
    for vehicle in vehicles:
        depreciation = vehicle.get_depreciation()
        if depreciation and vehicle.purchased_date:
            purchase_year = vehicle.purchased_date.year
            if purchase_year not in year_data:
                year_data[purchase_year] = {'year': purchase_year, 'fuel': 0, 'maintenance': 0, 'insurance': 0, 'registration': 0, 'vehicle_cost': 0, 'vehicle_count': 0}
            year_data[purchase_year]['vehicle_cost'] += float(depreciation)

    # Convert to list and calculate totals
    year_stats_list = []
    for year, data in year_data.items():
        total = data['fuel'] + data['maintenance'] + data['insurance'] + data['registration'] + data['vehicle_cost']
        year_stats_list.append({
            'year': year,
            'vehicle_count': round(data['vehicle_count'], 1),
            'fuel': round(data['fuel'], 2),
            'maintenance': round(data['maintenance'], 2),
            'insurance': round(data['insurance'], 2),
            'registration': round(data['registration'], 2),
            'vehicle_cost': round(data['vehicle_cost'], 2),
            'total': round(total, 2)
        })

    # Sort the list
    sort_key_map = {
        'year': lambda x: x['year'],
        'vehicle_count': lambda x: x['vehicle_count'],
        'fuel': lambda x: x['fuel'],
        'maintenance': lambda x: x['maintenance'],
        'insurance': lambda x: x['insurance'],
        'registration': lambda x: x['registration'],
        'vehicle_cost': lambda x: x['vehicle_cost'],
        'total': lambda x: x['total'],
    }

    if sort_by in sort_key_map:
        reverse_sort = (sort_dir == 'desc')
        year_stats_list.sort(key=sort_key_map[sort_by], reverse=reverse_sort)

    # Calculate min/max for highlighting (exclude zeros)
    min_max = {}
    if year_stats_list:
        stats_keys = ['vehicle_count', 'fuel', 'maintenance', 'insurance', 'registration', 'vehicle_cost', 'total']

        for key in stats_keys:
            values = [v[key] for v in year_stats_list if v[key] > 0]
            if values:
                min_max[f'{key}_min'] = min(values)
                min_max[f'{key}_max'] = max(values)

    log_event(
        request=request,
        event="Lifetime expense report viewed",
        level="DEBUG",
        year_count=len(year_stats_list),
        sort_by=sort_by
    )

    return render(request, "autolog/lifetime_expense_report.html", {
        'year_stats_list': year_stats_list,
        'sort_by': sort_by,
        'sort_dir': sort_dir,
        'min_max': min_max,
    })


@login_required
def vehicle_create(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.user = request.user
            vehicle.save()

            # Record down payment if provided
            if record_down_payment(vehicle):
                log_event(
                    request=request,
                    event="Down payment recorded",
                    level="INFO",
                    vehicle_id=vehicle.id,
                    amount=float(vehicle.down_payment)
                )

            log_event(
                request=request,
                event="Vehicle created",
                level="INFO",
                vehicle_id=vehicle.id,
                vehicle=str(vehicle)
            )
            return redirect('vehicle_detail', pk=vehicle.pk)
    else:
        form = VehicleForm()

    log_event(
        request=request,
        event="Vehicle create form accessed",
        level="DEBUG"
    )
    return render(request, "autolog/vehicle_form.html", {
        'form': form,
        'action': 'Add',
    })


@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    # Auto-generate loan payments if enabled
    payments_created = generate_loan_payments(vehicle)
    if payments_created > 0:
        log_event(
            request=request,
            event="Auto-generated loan payments",
            level="INFO",
            vehicle_id=vehicle.id,
            payments_created=payments_created
        )

    # Auto-generate lease payments if enabled
    lease_payments_created = generate_lease_payments(vehicle)
    if lease_payments_created > 0:
        log_event(
            request=request,
            event="Auto-generated lease payments",
            level="INFO",
            vehicle_id=vehicle.id,
            payments_created=lease_payments_created
        )

    fuel_entries = list(vehicle.fuel_entries.all())

    # Calculate distance traveled for each entry
    for i, entry in enumerate(fuel_entries):
        if i < len(fuel_entries) - 1:
            # Get previous entry (next in list since ordered by -date)
            prev_entry = fuel_entries[i + 1]
            entry.distance_traveled = entry.odometer - prev_entry.odometer
        elif vehicle.purchased_odometer:
            # First entry, use purchased odometer
            entry.distance_traveled = entry.odometer - vehicle.purchased_odometer
        else:
            # No previous data
            entry.distance_traveled = entry.odometer

    # Calculate control chart statistics
    chart_data = None
    chart_data_json = None
    if fuel_entries:
        # Get up to first 50 entries (oldest to newest for chronological order)
        chart_entries = list(reversed(fuel_entries[-50:]))

        is_electric = vehicle.fuel_type == 'electric'

        # Calculate average and standard deviation for MPG or MPGe
        if is_electric:
            efficiency_values = [float(entry.mpge) for entry in chart_entries if entry.mpge]
            metric_label = 'MPGe'
        else:
            efficiency_values = [float(entry.mpg) for entry in chart_entries if entry.mpg]
            metric_label = 'MPG'

        if efficiency_values:
            import statistics
            import json
            avg = statistics.mean(efficiency_values)
            std = statistics.stdev(efficiency_values) if len(efficiency_values) > 1 else 0

            chart_data = {
                'dates': [entry.date.strftime('%Y-%m-%d') for entry in chart_entries if (entry.mpge if is_electric else entry.mpg)],
                'efficiency_values': efficiency_values,
                'avg': round(avg, 1),
                'std_plus_3': round(avg + (3 * std), 1),
                'std_minus_3': round(avg - (3 * std), 1),
                'metric_label': metric_label,
            }
            chart_data_json = json.dumps(chart_data)

    log_event(
        request=request,
        event="Vehicle detail viewed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        vehicle=str(vehicle)
    )
    # Calculate depreciation and interest for display purposes
    cost_info = None
    depreciation = vehicle.get_depreciation()
    if depreciation is not None:
        interest_paid = vehicle.get_interest_paid_to_date() or 0

        cost_info = {
            'cost': round(depreciation, 2),
            'cost_with_interest': round(depreciation + float(interest_paid), 2),
            'interest_paid': interest_paid,
        }

    # Calculate comprehensive vehicle statistics
    from django.db.models import Sum, Avg
    from datetime import date

    vehicle_stats = None
    # Calculate stats for both purchased and leased vehicles
    start_date = vehicle.purchased_date or vehicle.lease_start_date
    if start_date:
        # Calculate days owned/leased
        end_date = vehicle.sold_date if vehicle.is_sold else date.today()
        days_owned = (end_date - start_date).days
        if days_owned == 0:
            days_owned = 1  # Prevent division by zero

        # Calculate miles driven
        miles_driven = 0
        start_odometer = vehicle.purchased_odometer

        if vehicle.is_sold and vehicle.sold_odometer:
            if start_odometer:
                miles_driven = vehicle.sold_odometer - start_odometer
            else:
                # For leases without start odometer, just use sold odometer
                miles_driven = vehicle.sold_odometer
        elif start_odometer:
            # Get latest odometer reading from fuel or maintenance entries
            latest_fuel = vehicle.fuel_entries.order_by('-odometer').first()
            latest_maintenance = vehicle.maintenance_entries.order_by('-odometer').first()

            latest_odometer = start_odometer
            if latest_fuel and latest_fuel.odometer > latest_odometer:
                latest_odometer = latest_fuel.odometer
            if latest_maintenance and latest_maintenance.odometer > latest_odometer:
                latest_odometer = latest_maintenance.odometer

            miles_driven = latest_odometer - start_odometer
        else:
            # No start odometer - use latest odometer reading as miles driven
            latest_fuel = vehicle.fuel_entries.order_by('-odometer').first()
            latest_maintenance = vehicle.maintenance_entries.order_by('-odometer').first()

            if latest_fuel:
                miles_driven = latest_fuel.odometer
            if latest_maintenance and latest_maintenance.odometer > miles_driven:
                miles_driven = latest_maintenance.odometer

        # Calculate total costs by category
        total_fuel = vehicle.fuel_entries.aggregate(total=Sum('cost'))['total'] or 0
        total_maintenance = vehicle.maintenance_entries.aggregate(total=Sum('cost'))['total'] or 0
        total_insurance = vehicle.other_expenses.filter(expense_type='insurance').aggregate(total=Sum('cost'))['total'] or 0
        total_registration = vehicle.other_expenses.filter(expense_type='registration').aggregate(total=Sum('cost'))['total'] or 0
        total_vehicle_payments = vehicle.other_expenses.filter(expense_type='vehicle_payment').aggregate(total=Sum('cost'))['total'] or 0

        # Maintenance breakdown by category
        maintenance_breakdown = {}
        for category_code, category_name in vehicle.maintenance_entries.model.CATEGORY_CHOICES:
            total = vehicle.maintenance_entries.filter(category=category_code).aggregate(total=Sum('cost'))['total'] or 0
            maintenance_breakdown[category_code] = total

        # Get vehicle cost (depreciation + all payments made)
        vehicle_cost = vehicle.get_vehicle_cost()

        # Total cost (all expenses)
        total_cost = vehicle_cost + float(total_fuel) + float(total_maintenance) + float(total_insurance) + float(total_registration)

        # Cost per day calculations
        total_cost_per_day = total_cost / days_owned if days_owned > 0 else 0
        vehicle_cost_per_day = vehicle_cost / days_owned if days_owned > 0 else 0
        cost_per_mile = total_cost / miles_driven if miles_driven > 0 else 0

        # Average MPG (or MPGe for electric vehicles)
        if vehicle.fuel_type == 'electric':
            avg_mpg = vehicle.fuel_entries.aggregate(avg=Avg('mpge'))['avg'] or 0
        else:
            avg_mpg = vehicle.fuel_entries.aggregate(avg=Avg('mpg'))['avg'] or 0

        vehicle_stats = {
            'days_owned': days_owned,
            'miles_driven': miles_driven,
            'vehicle_cost': round(vehicle_cost, 2),
            'total_fuel': round(float(total_fuel), 2),
            'total_maintenance': round(float(total_maintenance), 2),
            'total_insurance': round(float(total_insurance), 2),
            'total_registration': round(float(total_registration), 2),
            'total_cost': round(total_cost, 2),
            'total_cost_per_day': round(total_cost_per_day, 2),
            'vehicle_cost_per_day': round(vehicle_cost_per_day, 2),
            'cost_per_mile': round(cost_per_mile, 2),
            'avg_mpg': round(float(avg_mpg), 2) if avg_mpg else 0,
            'maintenance_breakdown': maintenance_breakdown,
        }

    # Loan information
    loan_info = None
    if vehicle.loan_start_date:
        loan_info = {
            'monthly_payment': vehicle.get_monthly_payment(),
            'payments_made': vehicle.get_loan_payments_made(),
            'payments_remaining': vehicle.get_loan_payments_remaining(),
            'total_interest': vehicle.get_total_loan_interest(),
            'interest_paid_to_date': vehicle.get_interest_paid_to_date(),
        }

    return render(request, "autolog/vehicle_detail.html", {
        'vehicle': vehicle,
        'fuel_entries': fuel_entries,
        'chart_data': chart_data,
        'chart_data_json': chart_data_json,
        'loan_info': loan_info,
        'cost_info': cost_info,
        'vehicle_stats': vehicle_stats,
    })


@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()

            # Record down payment if provided and not already recorded
            if record_down_payment(vehicle):
                log_event(
                    request=request,
                    event="Down payment recorded",
                    level="INFO",
                    vehicle_id=vehicle.id,
                    amount=float(vehicle.down_payment)
                )

            log_event(
                request=request,
                event="Vehicle updated",
                level="INFO",
                vehicle_id=vehicle.id,
                vehicle=str(vehicle)
            )
            return redirect('vehicle_detail', pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle)

    log_event(
        request=request,
        event="Vehicle edit form accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )
    return render(request, "autolog/vehicle_form.html", {
        'form': form,
        'action': 'Edit',
        'vehicle': vehicle,
    })


@login_required
def vehicle_delete(request, pk):
    """Delete a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    if request.method == 'POST':
        log_event(
            request=request,
            event="Vehicle deleted",
            level="INFO",
            vehicle_id=vehicle.id,
            vehicle=str(vehicle)
        )
        vehicle.delete()
        messages.success(request, f'Vehicle "{vehicle}" has been deleted successfully.')
        return redirect('vehicle_list')

    log_event(
        request=request,
        event="Vehicle delete confirmation accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )

    return render(request, 'autolog/vehicle_confirm_delete.html', {
        'vehicle': vehicle,
    })


@login_required
def fuel_entry_list(request, vehicle_pk):
    """Display fuel entries with MPG chart for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    fuel_entries = list(vehicle.fuel_entries.all())

    # Calculate distance traveled for each entry
    for i, entry in enumerate(fuel_entries):
        if i < len(fuel_entries) - 1:
            prev_entry = fuel_entries[i + 1]
            entry.distance_traveled = entry.odometer - prev_entry.odometer
        elif vehicle.purchased_odometer:
            entry.distance_traveled = entry.odometer - vehicle.purchased_odometer
        else:
            entry.distance_traveled = entry.odometer

    # Calculate control chart statistics
    chart_data = None
    chart_data_json = None
    if fuel_entries:
        chart_entries = list(reversed(fuel_entries[-50:]))
        is_electric = vehicle.fuel_type == 'electric'

        if is_electric:
            efficiency_values = [float(entry.mpge) for entry in chart_entries if entry.mpge]
            metric_label = 'MPGe'
        else:
            efficiency_values = [float(entry.mpg) for entry in chart_entries if entry.mpg]
            metric_label = 'MPG'

        if efficiency_values:
            import statistics
            import json
            avg = statistics.mean(efficiency_values)
            std = statistics.stdev(efficiency_values) if len(efficiency_values) > 1 else 0

            chart_data = {
                'dates': [entry.date.strftime('%Y-%m-%d') for entry in chart_entries if (entry.mpge if is_electric else entry.mpg)],
                'efficiency_values': efficiency_values,
                'avg': round(avg, 1),
                'std_plus_3': round(avg + (3 * std), 1),
                'std_minus_3': round(avg - (3 * std), 1),
                'metric_label': metric_label,
            }
            chart_data_json = json.dumps(chart_data)

    log_event(
        request=request,
        event="Fuel entry list viewed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )

    return render(request, "autolog/fuel_entry_list.html", {
        'vehicle': vehicle,
        'fuel_entries': fuel_entries,
        'chart_data': chart_data,
        'chart_data_json': chart_data_json,
    })


@login_required
def fuel_entry_create(request, vehicle_pk):
    """Create a new fuel entry for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    # Determine which form to use based on fuel type
    is_electric = vehicle.fuel_type == 'electric'
    FormClass = ElectricFuelForm if is_electric else GasolineFuelForm

    if request.method == 'POST':
        form = FormClass(request.POST, vehicle=vehicle)
        if form.is_valid():
            fuel_entry = form.save(commit=False)
            fuel_entry.vehicle = vehicle

            # Set calculated values from form's clean() method
            if is_electric:
                fuel_entry.mpge = form.cleaned_data.get('mpge')
                fuel_entry.cost = form.cleaned_data.get('cost')
            else:
                fuel_entry.mpg = form.cleaned_data.get('mpg')

            fuel_entry.save()

            log_event(
                request=request,
                event="Fuel entry created",
                level="INFO",
                vehicle_id=vehicle.id,
                vehicle=str(vehicle),
                fuel_entry_id=fuel_entry.id,
                mpg=fuel_entry.mpg,
                mpge=fuel_entry.mpge
            )

            return redirect('fuel_entry_detail', pk=fuel_entry.pk)
    else:
        form = FormClass(vehicle=vehicle)

    log_event(
        request=request,
        event="Fuel entry create form accessed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        is_electric=is_electric
    )

    return render(request, 'autolog/fuel_entry_form.html', {
        'form': form,
        'vehicle': vehicle,
        'is_electric': is_electric,
    })


@login_required
def fuel_entry_detail(request, pk):
    """Display details of a fuel entry"""
    fuel_entry = get_object_or_404(
        FuelEntry,
        pk=pk,
        vehicle__user=request.user
    )

    log_event(
        request=request,
        event="Fuel entry detail viewed",
        level="DEBUG",
        fuel_entry_id=fuel_entry.id,
        vehicle_id=fuel_entry.vehicle.id
    )

    return render(request, 'autolog/fuel_entry_detail.html', {
        'fuel_entry': fuel_entry,
        'vehicle': fuel_entry.vehicle,
    })


@login_required
def fuel_entry_edit(request, pk):
    """Edit an existing fuel entry"""
    fuel_entry = get_object_or_404(
        FuelEntry,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = fuel_entry.vehicle

    # Determine which form to use based on fuel type
    is_electric = vehicle.fuel_type == 'electric'
    FormClass = ElectricFuelForm if is_electric else GasolineFuelForm

    if request.method == 'POST':
        form = FormClass(request.POST, vehicle=vehicle, instance=fuel_entry)
        if form.is_valid():
            fuel_entry = form.save(commit=False)

            # Set calculated values from form's clean() method
            if is_electric:
                fuel_entry.mpge = form.cleaned_data.get('mpge')
                fuel_entry.cost = form.cleaned_data.get('cost')
            else:
                fuel_entry.mpg = form.cleaned_data.get('mpg')

            fuel_entry.save()

            log_event(
                request=request,
                event="Fuel entry updated",
                level="INFO",
                vehicle_id=vehicle.id,
                fuel_entry_id=fuel_entry.id
            )

            return redirect('vehicle_detail', pk=vehicle.pk)
    else:
        form = FormClass(vehicle=vehicle, instance=fuel_entry)

    log_event(
        request=request,
        event="Fuel entry edit form accessed",
        level="DEBUG",
        fuel_entry_id=fuel_entry.id
    )

    return render(request, 'autolog/fuel_entry_form.html', {
        'form': form,
        'vehicle': vehicle,
        'is_electric': is_electric,
        'fuel_entry': fuel_entry,
    })


@login_required
def fuel_entry_delete(request, pk):
    """Delete a fuel entry"""
    fuel_entry = get_object_or_404(
        FuelEntry,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = fuel_entry.vehicle

    if request.method == 'POST':
        log_event(
            request=request,
            event="Fuel entry deleted",
            level="INFO",
            vehicle_id=vehicle.id,
            fuel_entry_id=fuel_entry.id
        )
        fuel_entry.delete()
        return redirect('vehicle_detail', pk=vehicle.pk)

    log_event(
        request=request,
        event="Fuel entry delete confirmation accessed",
        level="DEBUG",
        fuel_entry_id=fuel_entry.id
    )

    return render(request, 'autolog/fuel_entry_confirm_delete.html', {
        'fuel_entry': fuel_entry,
        'vehicle': vehicle,
    })


# Maintenance Entry Views

@login_required
def maintenance_entry_list(request, vehicle_pk):
    """Display all maintenance entries for a vehicle with category filtering"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    # Get filter category from query params
    filter_category = request.GET.get('category', '')

    # Get all maintenance entries
    entries = vehicle.maintenance_entries.all()

    # Apply category filter if specified
    if filter_category and filter_category != 'all':
        entries = entries.filter(category=filter_category)

    # Calculate totals by category
    from django.db.models import Sum
    totals_by_category = {}
    for category_code, category_name in MaintenanceEntry.CATEGORY_CHOICES:
        total = vehicle.maintenance_entries.filter(category=category_code).aggregate(
            total_cost=Sum('cost')
        )['total_cost'] or 0
        totals_by_category[category_code] = {
            'name': category_name,
            'total': total,
            'count': vehicle.maintenance_entries.filter(category=category_code).count()
        }

    log_event(
        request=request,
        event="Maintenance entry list viewed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        filter_category=filter_category,
        entry_count=entries.count()
    )

    return render(request, 'autolog/maintenance_entry_list.html', {
        'vehicle': vehicle,
        'entries': entries,
        'filter_category': filter_category,
        'totals_by_category': totals_by_category,
        'categories': MaintenanceEntry.CATEGORY_CHOICES,
    })


@login_required
def maintenance_entry_create(request, vehicle_pk):
    """Create a new maintenance entry for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST':
        form = MaintenanceEntryForm(request.POST, vehicle=vehicle)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.vehicle = vehicle
            entry.save()

            log_event(
                request=request,
                event="Maintenance entry created",
                level="INFO",
                vehicle_id=vehicle.id,
                entry_id=entry.id,
                category=entry.category,
                cost=float(entry.cost)
            )

            return redirect('maintenance_entry_list', vehicle_pk=vehicle.pk)
    else:
        form = MaintenanceEntryForm(vehicle=vehicle)

    log_event(
        request=request,
        event="Maintenance entry create form accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )

    return render(request, 'autolog/maintenance_entry_form.html', {
        'form': form,
        'vehicle': vehicle,
        'action': 'Add',
    })


@login_required
def maintenance_entry_edit(request, pk):
    """Edit an existing maintenance entry"""
    entry = get_object_or_404(
        MaintenanceEntry,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = entry.vehicle

    if request.method == 'POST':
        form = MaintenanceEntryForm(request.POST, vehicle=vehicle, instance=entry)
        if form.is_valid():
            entry = form.save()

            log_event(
                request=request,
                event="Maintenance entry updated",
                level="INFO",
                vehicle_id=vehicle.id,
                entry_id=entry.id,
                category=entry.category
            )

            return redirect('maintenance_entry_list', vehicle_pk=vehicle.pk)
    else:
        form = MaintenanceEntryForm(vehicle=vehicle, instance=entry)

    log_event(
        request=request,
        event="Maintenance entry edit form accessed",
        level="DEBUG",
        entry_id=entry.id
    )

    return render(request, 'autolog/maintenance_entry_form.html', {
        'form': form,
        'vehicle': vehicle,
        'action': 'Edit',
        'entry': entry,
    })


@login_required
def maintenance_entry_delete(request, pk):
    """Delete a maintenance entry"""
    entry = get_object_or_404(
        MaintenanceEntry,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = entry.vehicle

    if request.method == 'POST':
        log_event(
            request=request,
            event="Maintenance entry deleted",
            level="INFO",
            vehicle_id=vehicle.id,
            entry_id=entry.id,
            category=entry.category
        )
        entry.delete()
        return redirect('maintenance_entry_list', vehicle_pk=vehicle.pk)

    log_event(
        request=request,
        event="Maintenance entry delete confirmation accessed",
        level="DEBUG",
        entry_id=entry.id
    )

    return render(request, 'autolog/maintenance_entry_confirm_delete.html', {
        'entry': entry,
        'vehicle': vehicle,
    })


# Other Expense Views (Insurance, Registration)

@login_required
def other_expense_list(request, vehicle_pk):
    """Display all other expenses (insurance, registration) for a vehicle with type filtering"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    # Get filter type from query params
    filter_type = request.GET.get('type', '')

    # Get all other expenses
    expenses = vehicle.other_expenses.all()

    # Apply type filter if specified
    if filter_type and filter_type != 'all':
        expenses = expenses.filter(expense_type=filter_type)

    # Calculate totals by type
    from django.db.models import Sum
    totals_by_type = {}
    for type_code, type_name in OtherExpense.EXPENSE_TYPE_CHOICES:
        total = vehicle.other_expenses.filter(expense_type=type_code).aggregate(
            total_cost=Sum('cost')
        )['total_cost'] or 0
        totals_by_type[type_code] = {
            'name': type_name,
            'total': total,
            'count': vehicle.other_expenses.filter(expense_type=type_code).count()
        }

    log_event(
        request=request,
        event="Other expenses list viewed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        filter_type=filter_type,
        expense_count=expenses.count()
    )

    return render(request, 'autolog/other_expense_list.html', {
        'vehicle': vehicle,
        'expenses': expenses,
        'filter_type': filter_type,
        'totals_by_type': totals_by_type,
        'expense_types': OtherExpense.EXPENSE_TYPE_CHOICES,
    })


@login_required
def other_expense_create(request, vehicle_pk):
    """Create a new other expense for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST':
        form = OtherExpenseForm(request.POST, vehicle=vehicle)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.vehicle = vehicle
            expense.save()

            log_event(
                request=request,
                event="Other expense created",
                level="INFO",
                vehicle_id=vehicle.id,
                expense_id=expense.id,
                expense_type=expense.expense_type,
                cost=float(expense.cost)
            )

            return redirect('other_expense_list', vehicle_pk=vehicle.pk)
    else:
        form = OtherExpenseForm(vehicle=vehicle)

    log_event(
        request=request,
        event="Other expense create form accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )

    return render(request, 'autolog/other_expense_form.html', {
        'form': form,
        'vehicle': vehicle,
        'action': 'Add',
    })


@login_required
def other_expense_edit(request, pk):
    """Edit an existing other expense"""
    expense = get_object_or_404(
        OtherExpense,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = expense.vehicle

    if request.method == 'POST':
        form = OtherExpenseForm(request.POST, vehicle=vehicle, instance=expense)
        if form.is_valid():
            expense = form.save()

            log_event(
                request=request,
                event="Other expense updated",
                level="INFO",
                vehicle_id=vehicle.id,
                expense_id=expense.id,
                expense_type=expense.expense_type
            )

            return redirect('other_expense_list', vehicle_pk=vehicle.pk)
    else:
        form = OtherExpenseForm(vehicle=vehicle, instance=expense)

    log_event(
        request=request,
        event="Other expense edit form accessed",
        level="DEBUG",
        expense_id=expense.id
    )

    return render(request, 'autolog/other_expense_form.html', {
        'form': form,
        'vehicle': vehicle,
        'action': 'Edit',
        'expense': expense,
    })


@login_required
def other_expense_delete(request, pk):
    """Delete an other expense"""
    expense = get_object_or_404(
        OtherExpense,
        pk=pk,
        vehicle__user=request.user
    )
    vehicle = expense.vehicle

    if request.method == 'POST':
        log_event(
            request=request,
            event="Other expense deleted",
            level="INFO",
            vehicle_id=vehicle.id,
            expense_id=expense.id,
            expense_type=expense.expense_type
        )
        expense.delete()
        return redirect('other_expense_list', vehicle_pk=vehicle.pk)

    log_event(
        request=request,
        event="Other expense delete confirmation accessed",
        level="DEBUG",
        expense_id=expense.id
    )

    return render(request, 'autolog/other_expense_confirm_delete.html', {
        'expense': expense,
        'vehicle': vehicle,
    })

# Vehicle Image Views
@login_required
def vehicle_images(request, vehicle_pk):
    """View and manage images for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)
    images = vehicle.images.all()
    
    # Handle image upload
    if request.method == 'POST':
        try:
            files = request.FILES.getlist('images')

            if not files:
                messages.error(request, 'Please select at least one image to upload.')
            else:
                # Check total image count
                current_count = images.count()
                max_images = settings.MAX_VEHICLE_IMAGES

                if current_count + len(files) > max_images:
                    messages.error(request, f'Cannot upload {len(files)} images. Maximum {max_images} images per vehicle. You currently have {current_count} images.')
                else:
                    uploaded_count = 0
                    for f in files:
                        VehicleImage.objects.create(
                            vehicle=vehicle,
                            image=f
                        )
                        uploaded_count += 1

                    messages.success(request, f'Successfully uploaded {uploaded_count} image(s).')

                    log_event(
                        request=request,
                        event="Vehicle images uploaded",
                        level="INFO",
                        vehicle_id=vehicle.id,
                        count=uploaded_count
                    )

                    return redirect('vehicle_images', vehicle_pk=vehicle.pk)
        except Exception as e:
            messages.error(request, f'Error uploading images: {str(e)}')
            log_event(
                request=request,
                event="Vehicle image upload failed",
                level="ERROR",
                vehicle_id=vehicle.id,
                error=str(e)
            )

        form = MultipleImageUploadForm()
    else:
        form = MultipleImageUploadForm()
    
    log_event(
        request=request,
        event="Vehicle images viewed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        image_count=images.count()
    )
    
    current_count = images.count()
    max_images = settings.MAX_VEHICLE_IMAGES

    return render(request, "autolog/vehicle_images.html", {
        'vehicle': vehicle,
        'images': images,
        'form': form,
        'max_images': max_images,
        'current_count': current_count,
        'remaining_count': max_images - current_count,
    })


@login_required
def vehicle_image_delete(request, pk):
    """Delete a vehicle image"""
    image = get_object_or_404(VehicleImage, pk=pk, vehicle__user=request.user)
    vehicle = image.vehicle
    
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Image deleted successfully.')
        
        log_event(
            request=request,
            event="Vehicle image deleted",
            level="INFO",
            vehicle_id=vehicle.id,
            image_id=pk
        )
        
        return redirect('vehicle_images', vehicle_pk=vehicle.pk)
    
    return render(request, "autolog/vehicle_image_confirm_delete.html", {
        'image': image,
        'vehicle': vehicle,
    })


@login_required
def vehicle_image_set_primary(request, pk):
    """Set an image as the primary image"""
    image = get_object_or_404(VehicleImage, pk=pk, vehicle__user=request.user)
    vehicle = image.vehicle
    
    # Unset all other primary images for this vehicle
    vehicle.images.update(is_primary=False)
    
    # Set this image as primary
    image.is_primary = True
    image.save()
    
    messages.success(request, 'Primary image updated.')
    
    log_event(
        request=request,
        event="Primary vehicle image set",
        level="INFO",
        vehicle_id=vehicle.id,
        image_id=pk
    )
    
    return redirect('vehicle_images', vehicle_pk=vehicle.pk)


@login_required
def vehicle_image_update_caption(request, pk):
    """Update image caption"""
    image = get_object_or_404(VehicleImage, pk=pk, vehicle__user=request.user)
    vehicle = image.vehicle
    
    if request.method == 'POST':
        caption = request.POST.get('caption', '').strip()
        image.caption = caption
        image.save()
        
        messages.success(request, 'Caption updated.')
        
        log_event(
            request=request,
            event="Vehicle image caption updated",
            level="DEBUG",
            vehicle_id=vehicle.id,
            image_id=pk
        )
        
        return redirect('vehicle_images', vehicle_pk=vehicle.pk)

    return redirect('vehicle_images', vehicle_pk=vehicle.pk)


@login_required
def export_all_data(request):
    """Export all vehicles and related data to JSON"""
    import json
    from django.http import JsonResponse, HttpResponse
    from decimal import Decimal

    vehicles = Vehicle.objects.filter(user=request.user).prefetch_related(
        'fuel_entries',
        'maintenance_entries',
        'other_expenses'
    )

    def serialize_date(d):
        """Convert date to string format"""
        return d.strftime('%Y-%m-%d') if d else None

    def serialize_decimal(d):
        """Convert Decimal to string"""
        return str(d) if d else None

    export_data = {
        'exportDate': serialize_date(date.today()),
        'vehicles': []
    }

    for vehicle in vehicles:
        vehicle_data = {
            'year': vehicle.year,
            'make': vehicle.make,
            'model': vehicle.model,
            'color': vehicle.color or None,
            'vinNumber': vehicle.vin_number or None,
            'licensePlateNumber': vehicle.license_plate_number or None,
            'registrationNumber': vehicle.registration_number or None,
            'state': vehicle.state or None,
            'purchasedDate': serialize_date(vehicle.purchased_date),
            'purchasedPrice': serialize_decimal(vehicle.purchased_price),
            'purchasedOdometer': vehicle.purchased_odometer,
            'dealerName': vehicle.dealer_name or None,
            'soldDate': serialize_date(vehicle.sold_date),
            'soldPrice': serialize_decimal(vehicle.sold_price),
            'soldOdometer': vehicle.sold_odometer,
            'currentValue': serialize_decimal(vehicle.current_value),
            'currentValueDate': serialize_date(vehicle.current_value_date),
            'fuelType': vehicle.fuel_type,
            'financingType': vehicle.financing_type,
            'downPayment': serialize_decimal(vehicle.down_payment),
            'fuelEntries': [],
            'maintenanceEntries': [],
            'otherExpenses': []
        }

        # Add loan information if applicable
        if vehicle.financing_type == 'loan' and vehicle.loan_start_date:
            vehicle_data['loanInfo'] = {
                'loanStartDate': serialize_date(vehicle.loan_start_date),
                'loanAmount': serialize_decimal(vehicle.loan_amount),
                'loanInterestRate': serialize_decimal(vehicle.loan_interest_rate),
                'loanTermMonths': vehicle.loan_term_months,
                'loanPaymentDay': vehicle.loan_payment_day,
                'loanAutoPayment': vehicle.loan_auto_payment
            }

        # Add lease information if applicable
        if vehicle.financing_type == 'lease' and vehicle.lease_start_date:
            vehicle_data['leaseInfo'] = {
                'leaseStartDate': serialize_date(vehicle.lease_start_date),
                'leasePaymentAmount': serialize_decimal(vehicle.lease_payment_amount),
                'leaseTermMonths': vehicle.lease_term_months,
                'leasePaymentDay': vehicle.lease_payment_day,
                'leaseAutoPayment': vehicle.lease_auto_payment
            }

        # Export fuel entries
        for fuel_entry in vehicle.fuel_entries.all():
            if vehicle.fuel_type == 'electric':
                fuel_data = {
                    'date': serialize_date(fuel_entry.date),
                    'odometer': fuel_entry.odometer,
                    'kwhPerMile': serialize_decimal(fuel_entry.kwh_per_mile),
                    'costPerKwh': serialize_decimal(fuel_entry.cost_per_kwh),
                    'costPerGallonReference': serialize_decimal(fuel_entry.cost_per_gallon_reference)
                }
            else:
                fuel_data = {
                    'date': serialize_date(fuel_entry.date),
                    'odometer': fuel_entry.odometer,
                    'gallons': serialize_decimal(fuel_entry.gallons),
                    'cost': serialize_decimal(fuel_entry.cost)
                }
            vehicle_data['fuelEntries'].append(fuel_data)

        # Export maintenance entries
        for maint_entry in vehicle.maintenance_entries.all():
            maint_data = {
                'date': serialize_date(maint_entry.date),
                'odometer': maint_entry.odometer,
                'category': maint_entry.category,
                'cost': serialize_decimal(maint_entry.cost),
                'notes': maint_entry.notes or None
            }
            vehicle_data['maintenanceEntries'].append(maint_data)

        # Export other expenses
        for expense in vehicle.other_expenses.all():
            expense_data = {
                'date': serialize_date(expense.date),
                'expenseType': expense.expense_type,
                'cost': serialize_decimal(expense.cost),
                'notes': expense.notes or None
            }
            vehicle_data['otherExpenses'].append(expense_data)

        export_data['vehicles'].append(vehicle_data)

    # Create JSON response with file download
    response = HttpResponse(
        json.dumps(export_data, indent=2),
        content_type='application/json'
    )
    filename = f'jautolog_export_{date.today().strftime("%Y%m%d")}.json'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    log_event(
        request=request,
        event="Data exported",
        level="INFO",
        vehicle_count=len(export_data['vehicles'])
    )

    return response


@login_required
def export_images(request):
    """Export all vehicle images as a ZIP file"""
    import zipfile
    from io import BytesIO
    from django.http import HttpResponse

    # Get all vehicles for the user
    vehicles = Vehicle.objects.filter(user=request.user).prefetch_related('images')

    # Create ZIP file in memory
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        image_count = 0

        for vehicle in vehicles:
            # Create folder name for this vehicle
            vehicle_folder = f"{vehicle.year}_{vehicle.make}_{vehicle.model}".replace(' ', '_')

            for idx, image in enumerate(vehicle.images.all(), 1):
                try:
                    # Read image file from storage (works with both S3 and local)
                    image_file = image.image.open('rb')
                    image_data = image_file.read()
                    image_file.close()

                    # Get file extension
                    file_ext = image.image.name.split('.')[-1] if '.' in image.image.name else 'jpg'

                    # Create filename with vehicle info
                    if image.caption:
                        # Sanitize caption for filename
                        safe_caption = "".join(c for c in image.caption if c.isalnum() or c in (' ', '-', '_')).strip()
                        filename = f"{vehicle_folder}/{idx:02d}_{safe_caption[:50]}.{file_ext}"
                    else:
                        filename = f"{vehicle_folder}/{idx:02d}_image.{file_ext}"

                    # Add to ZIP
                    zip_file.writestr(filename, image_data)
                    image_count += 1

                except Exception as e:
                    # Log error but continue with other images
                    log_event(
                        request=request,
                        event="Failed to export image",
                        level="WARNING",
                        vehicle_id=vehicle.id,
                        image_id=image.id,
                        error=str(e)
                    )
                    continue

    # Prepare response
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    filename = f'jautolog_images_{date.today().strftime("%Y%m%d")}.zip'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    log_event(
        request=request,
        event="Images exported",
        level="INFO",
        image_count=image_count,
        vehicle_count=vehicles.count()
    )

    return response
