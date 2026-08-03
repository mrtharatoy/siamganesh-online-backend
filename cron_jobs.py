"""Entry point for Render Cron Jobs (SG-B-3xx).

Each cron job that used to run inside the web service's in-process
APScheduler now runs as its own short-lived Render Cron Job invocation:
`python cron_jobs.py <group>`. This decouples job execution from the
gunicorn worker lifecycle -- a worker restart can no longer silently drop a
scheduled job, since there is no long-running scheduler thread to lose.

Groups mirror the original schedule:
  afternoon -- 16:00 Asia/Bangkok: print-queue digests, all owners
  evening   -- 21:00 Asia/Bangkok: daily summaries + photo-delivery follow-ups
  monthly   -- 21:00 Asia/Bangkok, last day of the month: muteteam monthly summary
"""
import sys
from datetime import datetime, timedelta, timezone

from app import (
    laos_daily_summary,
    laos_photo_delivery_followup,
    laos_print_queue_digest,
    mahabucha_daily_summary,
    mahabucha_photo_delivery_followup,
    mahabucha_print_queue_digest,
    muteteam_ceremony_daily_summary,
    muteteam_ceremony_photo_delivery_followup,
    muteteam_ceremony_print_queue_digest,
    muteteam_monthly_summary,
    muteteam_print_queue_digest,
    ratchaprasong_daily_summary,
    ratchaprasong_photo_delivery_followup,
    ratchaprasong_print_queue_digest,
)

JOB_GROUPS = {
    "afternoon": [
        mahabucha_print_queue_digest,
        muteteam_print_queue_digest,
        muteteam_ceremony_print_queue_digest,
        laos_print_queue_digest,
        ratchaprasong_print_queue_digest,
    ],
    "evening": [
        mahabucha_daily_summary,
        muteteam_ceremony_daily_summary,
        laos_daily_summary,
        ratchaprasong_daily_summary,
        mahabucha_photo_delivery_followup,
        muteteam_ceremony_photo_delivery_followup,
        laos_photo_delivery_followup,
        ratchaprasong_photo_delivery_followup,
    ],
}


def run_group(name):
    for job in JOB_GROUPS[name]:
        try:
            job()
        except Exception as error:
            print(f"❌ [CRON] {job.__name__} failed: {error}")


def run_monthly():
    # Render cron can't express "last day of month" directly, so this job
    # is scheduled for the 28th-31st and skips every day except the actual
    # last one (found by checking whether tomorrow rolls over to day 1).
    tz = timezone(timedelta(hours=7))
    today = datetime.now(tz).date()
    if (today + timedelta(days=1)).day != 1:
        print(f"[CRON] {today.isoformat()} is not the last day of the month, skipping.")
        return
    try:
        muteteam_monthly_summary()
    except Exception as error:
        print(f"❌ [CRON] muteteam_monthly_summary failed: {error}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in (*JOB_GROUPS, "monthly"):
        print("Usage: python cron_jobs.py <afternoon|evening|monthly>")
        sys.exit(1)

    group = sys.argv[1]
    if group == "monthly":
        run_monthly()
    else:
        run_group(group)
