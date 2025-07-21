from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme


class NextRedirectMiddleware:
    """Redirect to ?next= after any successful action."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and isinstance(response, HttpResponseRedirect):
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                response['Location'] = next_url
        return response
