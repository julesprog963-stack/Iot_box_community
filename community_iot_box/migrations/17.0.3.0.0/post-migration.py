import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Starting post-migration for community_iot_box 17.0.3.0.0...")

    # Mark pending or processing jobs without box_id as error
    cr.execute(
        """
        UPDATE community_iot_box_iot_job
           SET state = 'error',
               error_code = 'IOT_MISSING_BOX',
               error_message = 'Job created without box_id cannot be processed by any IoT Box.',
               result_status = 'error',
               result_message = 'Job created without box_id cannot be processed by any IoT Box.',
               processed_at = NOW(),
               write_date = NOW()
         WHERE state IN ('pending', 'processing')
           AND box_id IS NULL
    """
    )
    affected_missing_box = cr.rowcount
    if affected_missing_box:
        _logger.info(
            "Marked %s pending/processing jobs without box_id as error.",
            affected_missing_box,
        )

    # Recover abandoned jobs with a valid box_id that have lease_expires_at null or expired
    cr.execute(
        """
        UPDATE community_iot_box_iot_job
           SET state = 'pending',
               claimed_at = NULL,
               lease_expires_at = NULL,
               lock_token = NULL,
               write_date = NOW()
         WHERE box_id IS NOT NULL
           AND state = 'processing'
           AND (
               lease_expires_at < NOW()
               OR (
                   lease_expires_at IS NULL
                   AND write_date < NOW() - INTERVAL '900 seconds'
               )
           )
    """
    )
    affected_abandoned = cr.rowcount
    if affected_abandoned:
        _logger.info(
            "Returned %s abandoned processing jobs to pending state.",
            affected_abandoned,
        )

    _logger.info("Completed post-migration for community_iot_box 17.0.3.0.0.")
