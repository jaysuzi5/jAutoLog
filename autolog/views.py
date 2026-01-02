from django.shortcuts import render, redirect, get_object_or_404
from config.logging_utils import log_event
from django.contrib.auth.decorators import login_required
from .models import Vehicle
from .forms import VehicleForm


@login_required
def home(request):
    log_event(
        request=request,
        event="Home view was accessed in jautolog",
        level="DEBUG"
    )
    return render(request, "autolog/home.html")


@login_required
def vehicle_list(request):
    show_sold = request.GET.get('show_sold', 'false') == 'true'
    vehicles = Vehicle.objects.filter(user=request.user)

    if not show_sold:
        vehicles = vehicles.filter(sold_date__isnull=True)

    log_event(
        request=request,
        event="Vehicle list viewed",
        level="DEBUG",
        show_sold=show_sold,
        vehicle_count=vehicles.count()
    )
    return render(request, "autolog/vehicle_list.html", {
        'vehicles': vehicles,
        'show_sold': show_sold,
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
    log_event(
        request=request,
        event="Vehicle detail viewed",
        level="DEBUG",
        vehicle_id=vehicle.id,
        vehicle=str(vehicle)
    )
    return render(request, "autolog/vehicle_detail.html", {
        'vehicle': vehicle,
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