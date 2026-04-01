from django.shortcuts import render


class FriendlyNotFoundMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        expects_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in (request.headers.get('Accept') or '')
        )

        if response.status_code == 404 and not expects_json:
            if request.path.startswith('/static/') or request.path.startswith('/media/'):
                return response
            return render(
                request,
                'errors/404.html',
                {'requested_path': request.get_full_path()},
                status=404,
            )

        return response
