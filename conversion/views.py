import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from autolog.models import Vehicle, FuelEntry, MaintenanceEntry, OtherExpense
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
        # Check if file was uploaded
        json_file = request.FILES.get('json_file')
        json_text = request.POST.get('json_data', '').strip()

        if json_file:
            # Read from uploaded file
            try:
                json_text = json_file.read().decode('utf-8')
            except Exception as e:
                messages.error(request, f'Error reading file: {e}')
                return render(request, "conversion/vehicle_import.html")
        elif not json_text:
            messages.error(request, 'Please upload a file or provide JSON data.')
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
            # Don't populate text box if file was uploaded (confusing to user)
            return render(request, "conversion/vehicle_import.html", {
                'json_data': json_text if not json_file else ''
            })

        # Handle different import formats
        # Format 1: Export format with "vehicles" array: {"exportDate": "...", "vehicles": [...]}
        # Format 2: Array of vehicles: [{"year": 2023, ...}, ...]
        # Format 3: Single vehicle object: {"year": 2023, ...}

        if isinstance(data, dict) and 'vehicles' in data:
            # Export format
            vehicles_data = data['vehicles']
        elif isinstance(data, dict):
            # Single vehicle object
            vehicles_data = [data]
        elif isinstance(data, list):
            # Array of vehicles
            vehicles_data = data
        else:
            messages.error(request, 'JSON must be an object or array of objects.')
            # Don't populate text box if file was uploaded (confusing to user)
            return render(request, "conversion/vehicle_import.html", {
                'json_data': json_text if not json_file else ''
            })

        created_count = 0
        fuel_count = 0
        maintenance_count = 0
        expense_count = 0
        errors = []

        for idx, vehicle_data in enumerate(vehicles_data):
            try:
                # Import vehicle
                vehicle = create_vehicle_from_json(vehicle_data, request.user)
                vehicle.save()
                created_count += 1

                # Import fuel entries if present
                if 'fuelEntries' in vehicle_data and vehicle_data['fuelEntries']:
                    for fuel_data in vehicle_data['fuelEntries']:
                        try:
                            fuel_entry = create_fuel_entry_from_json(fuel_data, vehicle)
                            fuel_entry.save()
                            fuel_count += 1
                        except Exception as e:
                            errors.append(f"Vehicle {idx + 1} - Fuel entry error: {e}")

                # Import maintenance entries if present
                if 'maintenanceEntries' in vehicle_data and vehicle_data['maintenanceEntries']:
                    for maint_data in vehicle_data['maintenanceEntries']:
                        try:
                            # Extract category from data
                            category = maint_data.get('category')
                            if not category:
                                raise ValueError("Missing category in maintenance entry")
                            maint_entry = create_maintenance_entry_from_json(maint_data, vehicle, category)
                            maint_entry.save()
                            maintenance_count += 1
                        except Exception as e:
                            errors.append(f"Vehicle {idx + 1} - Maintenance entry error: {e}")

                # Import other expenses if present
                if 'otherExpenses' in vehicle_data and vehicle_data['otherExpenses']:
                    for expense_data in vehicle_data['otherExpenses']:
                        try:
                            # Extract expense type from data
                            expense_type = expense_data.get('expenseType')
                            if not expense_type:
                                raise ValueError("Missing expenseType in expense entry")
                            expense = create_other_expense_from_json(expense_data, vehicle, expense_type)
                            expense.save()
                            expense_count += 1
                        except Exception as e:
                            errors.append(f"Vehicle {idx + 1} - Expense error: {e}")

            except ValueError as e:
                errors.append(f"Vehicle {idx + 1}: {e}")
            except Exception as e:
                errors.append(f"Vehicle {idx + 1}: Unexpected error - {e}")

        # Build success message
        success_parts = []
        if created_count > 0:
            success_parts.append(f'{created_count} vehicle(s)')
        if fuel_count > 0:
            success_parts.append(f'{fuel_count} fuel entry(ies)')
        if maintenance_count > 0:
            success_parts.append(f'{maintenance_count} maintenance entry(ies)')
        if expense_count > 0:
            success_parts.append(f'{expense_count} expense(s)')

        if success_parts:
            messages.success(request, f'Successfully imported: {", ".join(success_parts)}.')
            log_event(
                request=request,
                event="Data imported",
                level="INFO",
                vehicles=created_count,
                fuel_entries=fuel_count,
                maintenance_entries=maintenance_count,
                expenses=expense_count
            )

        if errors:
            for error in errors:
                messages.error(request, error)
            log_event(
                request=request,
                event="Import had errors",
                level="WARNING",
                error_count=len(errors)
            )

        # Always redirect to vehicle list if any vehicles were created to prevent re-import
        if created_count > 0:
            return redirect('vehicle_list')

        # Only show the form again with data if nothing was imported and it was text input
        return render(request, "conversion/vehicle_import.html", {
            'json_data': json_text if not json_file else ''
        })

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
        'currentValue': 'current_value',
        'currentValueDate': 'current_value_date',
        'fuelType': 'fuel_type',
        'financingType': 'financing_type',
        'downPayment': 'down_payment',
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
            if model_key in ('purchased_date', 'sold_date', 'current_value_date'):
                if isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format for {json_key}: {value}. Use YYYY-MM-DD.")

            # Handle decimal fields
            elif model_key in ('purchased_price', 'sold_price', 'current_value', 'down_payment'):
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

    # Handle loan info if present
    if 'loanInfo' in data and data['loanInfo']:
        loan_info = data['loanInfo']
        loan_mapping = {
            'loanStartDate': 'loan_start_date',
            'loanAmount': 'loan_amount',
            'loanInterestRate': 'loan_interest_rate',
            'loanTermMonths': 'loan_term_months',
            'loanPaymentDay': 'loan_payment_day',
            'loanAutoPayment': 'loan_auto_payment',
        }

        for json_key, model_key in loan_mapping.items():
            if json_key in loan_info and loan_info[json_key] not in (None, ''):
                value = loan_info[json_key]

                # Handle date
                if model_key == 'loan_start_date':
                    if isinstance(value, str):
                        value = datetime.strptime(value, '%Y-%m-%d').date()

                # Handle decimal
                elif model_key in ('loan_amount', 'loan_interest_rate'):
                    value = Decimal(str(value))

                # Handle integer
                elif model_key in ('loan_term_months', 'loan_payment_day'):
                    value = int(value)

                # Handle boolean
                elif model_key == 'loan_auto_payment':
                    value = bool(value)

                vehicle_data[model_key] = value

    # Handle lease info if present
    if 'leaseInfo' in data and data['leaseInfo']:
        lease_info = data['leaseInfo']
        lease_mapping = {
            'leaseStartDate': 'lease_start_date',
            'leasePaymentAmount': 'lease_payment_amount',
            'leaseTermMonths': 'lease_term_months',
            'leasePaymentDay': 'lease_payment_day',
            'leaseAutoPayment': 'lease_auto_payment',
        }

        for json_key, model_key in lease_mapping.items():
            if json_key in lease_info and lease_info[json_key] not in (None, ''):
                value = lease_info[json_key]

                # Handle date
                if model_key == 'lease_start_date':
                    if isinstance(value, str):
                        value = datetime.strptime(value, '%Y-%m-%d').date()

                # Handle decimal
                elif model_key == 'lease_payment_amount':
                    value = Decimal(str(value))

                # Handle integer
                elif model_key in ('lease_term_months', 'lease_payment_day'):
                    value = int(value)

                # Handle boolean
                elif model_key == 'lease_auto_payment':
                    value = bool(value)

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


@login_required
def maintenance_entry_import(request, vehicle_pk):
    """Import maintenance entries for a specific vehicle from nested JSON data"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST':
        json_text = request.POST.get('json_data', '').strip()

        if not json_text:
            messages.error(request, 'Please provide JSON data.')
            return render(request, "conversion/maintenance_entry_import.html", {'vehicle': vehicle})

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            messages.error(request, f'Invalid JSON format: {e}')
            log_event(
                request=request,
                event="Maintenance entry import failed - invalid JSON",
                level="WARNING",
                vehicle_id=vehicle.id,
                error=str(e)
            )
            return render(request, "conversion/maintenance_entry_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        # Expect nested format: {"maintenance": {"oil": [...], "repairs": [...]}}
        if not isinstance(data, dict) or 'maintenance' not in data:
            messages.error(request, 'JSON must contain a "maintenance" object with category arrays.')
            return render(request, "conversion/maintenance_entry_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        maintenance_data = data['maintenance']
        if not isinstance(maintenance_data, dict):
            messages.error(request, 'The "maintenance" field must be an object with category keys.')
            return render(request, "conversion/maintenance_entry_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        created_count = 0
        errors = []

        # Valid categories
        valid_categories = ['oil', 'repairs', 'tires', 'wash', 'accessories']

        # Process each category
        for category, entries in maintenance_data.items():
            if category not in valid_categories:
                errors.append(f"Unknown category: {category}")
                continue

            if not isinstance(entries, list):
                errors.append(f"Category '{category}' must contain an array of entries")
                continue

            # Process each entry in this category
            for idx, entry_data in enumerate(entries):
                try:
                    entry = create_maintenance_entry_from_json(entry_data, vehicle, category)
                    entry.save()
                    created_count += 1
                except ValueError as e:
                    errors.append(f"{category.capitalize()} entry {idx + 1}: {e}")
                except Exception as e:
                    errors.append(f"{category.capitalize()} entry {idx + 1}: Unexpected error - {e}")

        if created_count > 0:
            messages.success(request, f'Successfully imported {created_count} maintenance entry(ies) for {vehicle}.')
            log_event(
                request=request,
                event="Maintenance entries imported",
                level="INFO",
                vehicle_id=vehicle.id,
                count=created_count
            )

        if errors:
            for error in errors:
                messages.error(request, error)
            log_event(
                request=request,
                event="Maintenance entry import had errors",
                level="WARNING",
                vehicle_id=vehicle.id,
                error_count=len(errors)
            )

        if created_count > 0 and not errors:
            return redirect('maintenance_entry_list', vehicle_pk=vehicle.pk)

        return render(request, "conversion/maintenance_entry_import.html", {
            'vehicle': vehicle,
            'json_data': json_text
        })

    log_event(
        request=request,
        event="Maintenance entry import page accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )
    return render(request, "conversion/maintenance_entry_import.html", {'vehicle': vehicle})


def create_maintenance_entry_from_json(data, vehicle, category):
    """Create MaintenanceEntry from JSON data"""

    # Field mapping (JSON camelCase -> model snake_case)
    field_mapping = {
        'date': 'date',
        'odometer': 'odometer',
        'cost': 'cost',
        'notes': 'notes',
    }

    # Required fields
    required_fields = ['date', 'odometer', 'cost']

    # Validate required fields
    for field in required_fields:
        if field not in data or data[field] in (None, ''):
            raise ValueError(f"Missing required field: {field}")

    entry_data = {'vehicle': vehicle, 'category': category}

    # Process fields with type conversion
    for json_key, model_key in field_mapping.items():
        if json_key in data and data[json_key] is not None:
            value = data[json_key]

            # Date conversion
            if model_key == 'date':
                if isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format for {json_key}: {value}. Use YYYY-MM-DD.")

            # Decimal conversion
            elif model_key == 'cost':
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Invalid cost format for {json_key}: {value}")

            # Integer conversion
            elif model_key == 'odometer':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid integer for {json_key}: {value}")

            # Notes: convert None to empty string
            elif model_key == 'notes' and value is None:
                value = ''

            entry_data[model_key] = value

    # Set notes to empty string if not provided
    if 'notes' not in entry_data:
        entry_data['notes'] = ''

    # Create entry
    entry = MaintenanceEntry(**entry_data)

    # Basic validation (no previous odometer check per user request)
    if entry.odometer < 0:
        raise ValueError(f"Odometer cannot be negative")

    if entry.odometer > 1000000:
        raise ValueError(f"Odometer cannot exceed 1,000,000 miles")

    # Validate cost
    if entry.cost > 50000:
        raise ValueError(f"Cost cannot exceed $50,000")

    if entry.cost < 0:
        raise ValueError(f"Cost cannot be negative")

    return entry


@login_required
def other_expense_import(request, vehicle_pk):
    """Import other expenses (insurance, registration) for a specific vehicle from JSON data"""
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, user=request.user)

    if request.method == 'POST':
        json_text = request.POST.get('json_data', '').strip()

        if not json_text:
            messages.error(request, 'Please provide JSON data.')
            return render(request, "conversion/other_expense_import.html", {'vehicle': vehicle})

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            messages.error(request, f'Invalid JSON format: {e}')
            log_event(
                request=request,
                event="Other expense import failed - invalid JSON",
                level="WARNING",
                vehicle_id=vehicle.id,
                error=str(e)
            )
            return render(request, "conversion/other_expense_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        # Expect flat format: {"insurance": [...], "registration": [...]}
        if not isinstance(data, dict):
            messages.error(request, 'JSON must be an object with "insurance" and/or "registration" arrays.')
            return render(request, "conversion/other_expense_import.html", {
                'vehicle': vehicle,
                'json_data': json_text
            })

        created_count = 0
        errors = []

        # Valid expense types
        valid_types = ['insurance', 'registration', 'loan']

        # Process each expense type
        for expense_type, entries in data.items():
            if expense_type not in valid_types:
                errors.append(f"Unknown expense type: {expense_type}")
                continue

            if not isinstance(entries, list):
                errors.append(f"Type '{expense_type}' must contain an array of entries")
                continue

            # Process each entry in this type
            for idx, entry_data in enumerate(entries):
                try:
                    expense = create_other_expense_from_json(entry_data, vehicle, expense_type)
                    expense.save()
                    created_count += 1
                except ValueError as e:
                    errors.append(f"{expense_type.capitalize()} entry {idx + 1}: {e}")
                except Exception as e:
                    errors.append(f"{expense_type.capitalize()} entry {idx + 1}: Unexpected error - {e}")

        if created_count > 0:
            messages.success(request, f'Successfully imported {created_count} expense entry(ies) for {vehicle}.')
            log_event(
                request=request,
                event="Other expenses imported",
                level="INFO",
                vehicle_id=vehicle.id,
                count=created_count
            )

        if errors:
            for error in errors:
                messages.error(request, error)
            log_event(
                request=request,
                event="Other expense import had errors",
                level="WARNING",
                vehicle_id=vehicle.id,
                error_count=len(errors)
            )

        if created_count > 0 and not errors:
            return redirect('other_expense_list', vehicle_pk=vehicle.pk)

        return render(request, "conversion/other_expense_import.html", {
            'vehicle': vehicle,
            'json_data': json_text
        })

    log_event(
        request=request,
        event="Other expense import page accessed",
        level="DEBUG",
        vehicle_id=vehicle.id
    )
    return render(request, "conversion/other_expense_import.html", {'vehicle': vehicle})


def create_other_expense_from_json(data, vehicle, expense_type):
    """Create OtherExpense from JSON data"""

    # Field mapping (JSON key -> model field)
    field_mapping = {
        'date': 'date',
        'cost': 'cost',
        'notes': 'notes',
    }

    # Required fields
    required_fields = ['date', 'cost']

    # Validate required fields
    for field in required_fields:
        if field not in data or data[field] in (None, ''):
            raise ValueError(f"Missing required field: {field}")

    entry_data = {'vehicle': vehicle, 'expense_type': expense_type}

    # Process fields with type conversion
    for json_key, model_key in field_mapping.items():
        if json_key in data and data[json_key] is not None:
            value = data[json_key]

            # Date conversion
            if model_key == 'date':
                if isinstance(value, str):
                    try:
                        value = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError(f"Invalid date format for {json_key}: {value}. Use YYYY-MM-DD.")

            # Decimal conversion
            elif model_key == 'cost':
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Invalid cost format for {json_key}: {value}")

            # Notes: convert None to empty string
            elif model_key == 'notes' and value is None:
                value = ''

            entry_data[model_key] = value

    # Set notes to empty string if not provided
    if 'notes' not in entry_data:
        entry_data['notes'] = ''

    # Create expense
    expense = OtherExpense(**entry_data)

    # Validate cost
    if expense.cost > 50000:
        raise ValueError(f"Cost cannot exceed $50,000")

    if expense.cost < 0:
        raise ValueError(f"Cost cannot be negative")

    return expense