from django.shortcuts import render
from config.logging_utils import log_event


def home(request):
    log_event(
        request=request,
        event="Home view was accessed in jautolog",
        level="DEBUG"
    )
    return render(request, "autolog/home.html")