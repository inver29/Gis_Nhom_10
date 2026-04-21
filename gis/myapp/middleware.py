from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render


class FriendlyNotFoundMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expects_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in (request.headers.get('Accept') or '')
        )

        try:
            response = self.get_response(request)
        except PermissionDenied as exc:
            if expects_json:
                return JsonResponse({'error': str(exc) or 'Bạn không có quyền truy cập.'}, status=403)
            return render(
                request,
                'errors/403.html',
                {'requested_path': request.get_full_path(), 'error_message': str(exc) if exc else ''},
                status=403,
            )

        if expects_json:
            return response

        if request.path.startswith('/static/') or request.path.startswith('/media/') or request.path.startswith('/db-media/'):
            return response

        if response.status_code == 400:
            return render(
                request,
                'errors/400.html',
                {'requested_path': request.get_full_path()},
                status=400,
            )

        if response.status_code == 404:
            return render(
                request,
                'errors/404.html',
                {'requested_path': request.get_full_path()},
                status=404,
            )

        if response.status_code == 405:
            return render(
                request,
                'errors/405.html',
                {'requested_path': request.get_full_path()},
                status=405,
            )

        return response
