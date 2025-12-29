from django.shortcuts import render

def conversion(request):
    return render(request, "conversion/conversion.html")