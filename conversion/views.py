import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from autolog.models import Vehicle, FuelEntry
from autolog.forms import get_previous_odometer
from config.logging_utils import log_event


@login_required
def conversion(request):
    log_event(
        request=request,
        event="Conversion page accessed",
        level="DEBUG"
    )
    return render(request, "conversion/conversion.html")


@login_required
def vehicle_import(request):
    if request.method == 'POST':
        json_text = request.POST.get('json_data', '').strip()

        if not json_text:
            messages.error(request, 'Please provide JSON data.')
            return render(request, "conversion/vehicle_import.html")

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            messages.error(request, f'Invalid JSON format: {e}')
            log_event(
                request=request,
                event="Vehicle import failed - invalid JSON",
                level="WARNING",
                error=str(e)
            )
            return render(request, "conversion/vehicle_import.html", {'json_data': json_text})

        # Handle both single object and array
        if isinstance(data, dict):
            vehicles_data = [data]
        elif isinstance(data, list):
            vehicles_data = data
        else:
            messages.error(request, 'JSON must be an object or array of objects.')
            return render(request, "conversion/vehicle_import.html", {'json_data': json_text})

        created_count = 0
        errors = []

        for idx, vehicle_data in enumerate(vehicles_data):
            try:
                vehicle = create_vehicle_from_json(vehicle_data, request.user)
                vehicle.save()
                created_count += 1
            except ValueError as e:
                errors.append(f"Vehicle {idx + 1}: {e}")
            except Exception as e:
                errors.append(f"Vehicle {idx + 1}: Unexpected error - {e}")

        if created_count > 0:
            messages.success(request, f'Successfully imported {created_count} vehicle(s).')
            log_event(
                request=request,
                event="Vehicles imported",
                level="INFO",
                count=created_count
            )

        if errors:
            for error in errors:
                messages.error(request, error)
            log_event(
                request=request,
                event="Vehicle import had errors",
                level="WARNING",
                error_count=len(errors)
            )

        if created_count > 0 and not errors:
            return redirect('vehicle_list')

        return render(request, "conversion/vehicle_import.html", {'json_data': json_text})

    log_event(
        request=request,
        event="Vehicle import page accessed",
        level="DEBUG"
    )
    return render(request, "conversion/vehicle_import.html")


def create_vehicle_from_json(data, user):
    """Create a Vehicle instance from JSON data with camelCase field names."""

    # Field mapping: JSON camelCase -> model snake_case
    field_mapping = {
        'year': 'year',
        'make': 'make',
        'model': 'model',
        'color': 'color',
        'vinNumber': 'vin_number',
        'licensePlateNumber': 'license_plate_number',
        'registrationNumber': 'registration_number',
        'state': 'state',
        'purchasedDate': 'purchased_date',
        'purchasedPrice': 'purchased_price',
        'purchasedOdometer': 'purchased_odometer',
        'dealerName': 'dealer_name',
        'soldDate': 'sold_date',
        'soldPrice': 'sold_price',
        'soldOdometer': 'sold_odometer',
        'fuelType': 'fuel_type',
    }

    # Valid fuel types
    valid_fuel_types = ['gasoline', 'diesel', 'electric', 'hybrid']

    # Required fields
    required_fields = ['year', 'make', 'model']

    # Check required fields
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Missing required field: {field}")

    vehicle_data = {'user': user}

    for json_key, model_key in field_mapping.items():
        if json_key in data and data[json_key] not in (None, ''):
            value = data[json_key]

            # Handle date fields
            if model_key in ('purchased_date', 'sold_date'):
                if isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format for {json_key}: {value}. Use YYYY-MM-DD.")

            # Handle decimal fields
            elif model_key in ('purchased_price', 'sold_price'):
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Invalid price format for {json_key}: {value}")

            # Handle integer fields
            elif model_key in ('year', 'purchased_odometer', 'sold_odometer'):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid integer for {json_key}: {value}")

            # Handle fuel type
            elif model_key == 'fuel_type':
                value = str(value).lower()
                if value not in valid_fuel_types:
                    raise ValueError(f"Invalid fuel type: {value}. Must be one of: {', '.join(valid_fuel_types)}")

            vehicle_data[model_key] = value

    return Vehicle(**vehicle_data)


@login_required
def fuel_entry_import(request, vehicle_pk):
    """Import fuel entries for a specific vehicle from JSON data"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST':
        json_text = request.POST.get('json_data', '').strip()

        if not json_text:
            messages.error(request, 'Please provide JSON data.')
            return render(request, "conversion/fuel_entry_import.html", {'vehicle': vehicle})

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            messages.error(request, f'Invalid JSON format: {e}')
            log_event(
                request=request,
                event="Fuel entry import failed - invalid JSON",
                level="WARNING",
                vehicle_id=vehicle.id,
                error=str(e)
            )
            return render(request, "conversion/fuel_entry_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        # Handle both single object and array
        if isinstance(data, dict):
            entries_data = [data]
        elif isinstance(data, list):
            entries_data = data
        else:
            messages.error(request, 'JSON must be an object or array of objects.')
            return render(request, "conversion/fuel_entry_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        created_count = 0
        errors = []

        for idx, entry_data in enumerate(entries_data):
            try:
                fuel_entry = create_fuel_entry_from_json(entry_data, vehicle)
                fuel_entry.save()
                created_count += 1
            except ValueError as e:
                errors.append(f"Entry {idx + 1}: {e}")
            except Exception as e:
                errors.append(f"Entry {idx + 1}: Unexpected error - {e}")

        if created_count > 0:
            messages.success(request, f'Successfully imported {created_count} fuel entry(ies) for {vehicle}.')
            log_event(
                request=request,
                event="Fuel entries imported",
                level="INFO",
                vehicle_id=vehicle.id,
                count=created_count
            )

        if errors:
            for error in errors:
                messages.error(request, error)
            log_event(
                request=request,
                event="Fuel entry import had errors",
                level="WARNING",
                vehicle_id=vehicle.id,
                error_count=len(errors)
            )

        if created_count > 0 and not errors:
            return redirect('vehicle_detail', pk=vehicle.pk)

        return render(request, "conversion/fuel_entry_import.html", {
            'vehicle': vehicle,
            'json_data': json_text
        })

    log_event(
        request=request,
        event="Fuel entry import page accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )
    return render(request, "conversion/fuel_entry_import.html", {'vehicle': vehicle})


def create_fuel_entry_from_json(data, vehicle):
    """Create a FuelEntry instance from JSON data with camelCase field names."""

    is_electric = vehicle.fuel_type == 'electric'

    # Field mapping for gasoline/diesel/hybrid
    gasoline_field_mapping = {
        'date': 'date',
        'odometer': 'odometer',
        'gallons': 'gallons',
        'cost': 'cost',
    }

    # Field mapping for electric vehicles
    electric_field_mapping = {
        'date': 'date',
        'odometer': 'odometer',
        'kwhPerMile': 'kwh_per_mile',
        'costPerKwh': 'cost_per_kwh',
        'costPerGallonReference': 'cost_per_gallon_reference',
    }

    # Select appropriate field mapping
    field_mapping = electric_field_mapping if is_electric else gasoline_field_mapping

    # Required fields
    if is_electric:
        required_fields = ['date', 'odometer', 'kwhPerMile', 'costPerKwh', 'costPerGallonReference']
    else:
        required_fields = ['date', 'odometer', 'gallons', 'cost']

    # Check required fields
    for field in required_fields:
        if field not in data or data[field] in (None, ''):
            raise ValueError(f"Missing required field: {field}")

    entry_data = {'vehicle': vehicle}

    for json_key, model_key in field_mapping.items():
        if json_key in data and data[json_key] not in (None, ''):
            value = data[json_key]

            # Handle date fields
            if model_key == 'date':
                if isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format for {json_key}: {value}. Use YYYY-MM-DD.")

            # Handle decimal fields
            elif model_key in ('gallons', 'cost', 'kwh_per_mile', 'cost_per_kwh', 'cost_per_gallon_reference'):
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Invalid decimal format for {json_key}: {value}")

            # Handle integer fields
            elif model_key == 'odometer':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid integer for {json_key}: {value}")

            entry_data[model_key] = value

    # Create the fuel entry
    fuel_entry = FuelEntry(**entry_data)

    # Validate odometer - get entry immediately before this one
    # Consider both earlier dates AND same date with lower odometer
    from django.db.models import Q
    prev_entry = vehicle.fuel_entries.filter(
        Q(date__lt=fuel_entry.date) |
        Q(date=fuel_entry.date, odometer__lt=fuel_entry.odometer)
    ).order_by('-date', '-odometer').first()

    if prev_entry:
        prev_odometer = prev_entry.odometer
    elif vehicle.purchased_odometer:
        prev_odometer = vehicle.purchased_odometer
    else:
        prev_odometer = 0
    if fuel_entry.odometer <= prev_odometer:
        raise ValueError(f"Odometer ({fuel_entry.odometer}) must be greater than previous ({prev_odometer})")

    max_diff = 10000 if is_electric else 1000
    if fuel_entry.odometer > prev_odometer + max_diff:
        raise ValueError(
            f"Odometer ({fuel_entry.odometer}) cannot be more than {max_diff} miles "
            f"greater than previous ({prev_odometer})"
        )

    # Calculate and validate MPG/MPGe
    if is_electric:
        # Validate electric-specific fields
        if fuel_entry.kwh_per_mile < 0.100 or fuel_entry.kwh_per_mile > 0.500:
            raise ValueError(f"KWH per mile must be between 0.100 and 0.500")

        if fuel_entry.cost_per_kwh < 0.050 or fuel_entry.cost_per_kwh > 0.500:
            raise ValueError(f"Cost per KWH must be between $0.050 and $0.500")

        if fuel_entry.cost_per_gallon_reference < 0.50 or fuel_entry.cost_per_gallon_reference > 20.00:
            raise ValueError(f"Reference gas price must be between $0.50 and $20.00")

        # Calculate MPGe
        mpge = float(fuel_entry.cost_per_gallon_reference) / (
            float(fuel_entry.kwh_per_mile) * float(fuel_entry.cost_per_kwh)
        )
        fuel_entry.mpge = round(mpge, 1)

        # Calculate total cost
        miles_driven = fuel_entry.odometer - prev_odometer
        total_cost = miles_driven * float(fuel_entry.kwh_per_mile) * float(fuel_entry.cost_per_kwh)
        fuel_entry.cost = round(total_cost, 2)
    else:
        # Validate gasoline-specific fields
        if fuel_entry.gallons > 100:
            raise ValueError(f"Gallons cannot exceed 100")

        if fuel_entry.cost > 500:
            raise ValueError(f"Cost cannot exceed $500")

        # Calculate MPG
        miles_driven = fuel_entry.odometer - prev_odometer
        mpg = miles_driven / float(fuel_entry.gallons)

        if mpg < 4.0:
            raise ValueError(f"Calculated MPG ({mpg:.2f}) is too low. Please verify odometer and gallons.")

        if mpg > 100.0:
            raise ValueError(f"Calculated MPG ({mpg:.2f}) is too high. Please verify odometer and gallons.")

        fuel_entry.mpg = round(mpg, 2)

    return fuel_entry