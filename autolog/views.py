from django.shortcuts import render, redirect, get_object_or_404
from config.logging_utils import log_event
from django.contrib.auth.decorators import login_required
from .models import Vehicle, FuelEntry
from .forms import VehicleForm, GasolineFuelForm, ElectricFuelForm


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
def vehicle_create(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.user = request.user
            vehicle.save()
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
    return render(request, "autolog/vehicle_detail.html", {
        'vehicle': vehicle,
        'fuel_entries': fuel_entries,
        'chart_data': chart_data,
        'chart_data_json': chart_data_json,
    })


@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)

    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
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
def fuel_entry_create(request, vehicle_pk):
    """Create a new fuel entry for a vehicle"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    # Prevent adding fuel to sold vehicles
    if vehicle.is_sold:
        log_event(
            request=request,
            event="Attempted to add fuel entry to sold vehicle",
            level="WARNING",
            vehicle_id=vehicle.id,
            vehicle=str(vehicle)
        )
        return redirect('vehicle_detail', pk=vehicle.pk)

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