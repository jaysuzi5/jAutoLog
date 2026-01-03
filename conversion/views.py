import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from autolog.models import Vehicle
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