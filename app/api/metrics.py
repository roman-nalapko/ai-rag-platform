from fastapi import APIRouter, Response

from app.core.metrics import metrics

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics exporter",
    response_class=Response,
    responses={
        200: {
            "content": {
                "text/plain; version=0.0.4; charset=utf-8": {},
            },
            "description": "Prometheus exposition text format",
        }
    },
)
def get_metrics() -> Response:
    return Response(
        content=metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
