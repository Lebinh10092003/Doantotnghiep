from django.shortcuts import render


# Create your views here.
def is_htmx_request(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )

def centers_manage(request):
    if is_htmx_request(request):
        return render(request, "centers_table.html")
    return render(request, "manage_centers.html")
