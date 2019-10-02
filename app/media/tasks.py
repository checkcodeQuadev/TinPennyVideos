from django.conf import settings
from celery.decorators import task, periodic_task
from celery.utils.log import get_task_logger

from .models import Video, Stream
from .utils import delete_sqs_message, retrieve_sqs_messages, parse_sqs_message

logger = get_task_logger(__name__)


@task(name="save_converted_video_urls")
def save_converted_video_urls():
    """Load convert result from SQS and save into database"""

    sqs_url = settings.AWS_MEDIACONVERT_SQS_URL
    msgs = retrieve_sqs_messages(sqs_url, 10, 5, 60)
    if msgs is None:
        return

    for msg in msgs:
        parsed = parse_sqs_message(msg, logger)
        if parsed is None:
            continue

        src_key, duration_in_ms, poster_thumbnail, playlist_paths = parsed

        try:
            video = Video.objects.get(origin=src_key)

        except Video.DoesNotExist:
            logger.info("Video not found for {}".format(src_key))
            delete_sqs_message(sqs_url, msg['ReceiptHandle'])
            continue

        for stream_path in playlist_paths:
            Stream.objects.create(path=stream_path, origin=video)

        video.duration_in_ms = duration_in_ms
        video.poster_thumbnail = poster_thumbnail
        video.mc_status = Video.SUCCEEDED
        video.save()

        delete_sqs_message(sqs_url, msg['ReceiptHandle'])
        logger.info("Successfully updated media convert success result for {}".format(src_key))