import logging
import pkg_resources

from flask import Flask, request, Response
from lintreview.config import load_config
from lintreview.github import handle_github_hook
from lintreview.gitlab import handle_gitlab_hook
from lintreview.tasks import cleanup_pull_request

config = load_config()
app = Flask("lintreview")
app.config.update(config)

log = logging.getLogger(__name__)
version = pkg_resources.get_distribution('lintreview').version


@app.route("/ping")
def ping():
    return "lint-review: %s pong\n" % (version,)


@app.route("/review/start", methods=["POST"])
def start_review():
    if not any(
            host_header in request.headers
            for host_header in ('X-GitHub-Event', 'X-GitLab-Event')):
        return Response(status=400)

    if 'X-GitHub-Event' in request.headers:
        return handle_github_hook()
    else:
        return handle_gitlab_hook()


def close_review(user, repo, pull_request):
    try:
        log.info("Scheduling cleanup for %s/%s", user, repo)
        cleanup_pull_request.delay(user, repo, pull_request['number'])
    except:
        log.error('Could not publish job to celery. '
                  'Make sure its running.')
    return Response(status=204)
