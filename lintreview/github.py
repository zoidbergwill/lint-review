from functools import partial
import logging

from flask import Response, request
import github3

log = logging.getLogger(__name__)

GITHUB_BASE_URL = 'https://api.github.com/'


def get_client(config):
    """
    Factory for the Github client
    """
    login = github3.login
    if config.get('GITHUB_URL', GITHUB_BASE_URL) != GITHUB_BASE_URL:
        login = partial(github3.enterprise_login, url=config['GITHUB_URL'])
    if 'GITHUB_OAUTH_TOKEN' in config:
        return login(username=config['GITHUB_USER'],
                     token=config['GITHUB_OAUTH_TOKEN'])
    return login(username=config['GITHUB_USER'],
                 password=config['GITHUB_PASSWORD'])


def get_repository(config, user, repo):
    gh = get_client(config)
    return gh.repository(owner=user, repository=repo)


def get_lintrc(repo, ref):
    """
    Download the .lintrc from a repo
    """
    log.info('Fetching lintrc file')
    response = repo.file_contents('.lintrc', ref)
    return response.decoded


def register_hook(repo, hook_url):
    """
    Register a new hook with a user's repository.
    """
    log.info('Registering webhook for %s on %s', hook_url, repo.full_name)
    hooks = repo.hooks()
    found = False
    for hook in hooks:
        if hook.name != 'web':
            continue
        if hook.config['url'] == hook_url:
            found = True
            break

    if found:
        msg = ("Found existing hook. "
               "No additional hooks registered.")
        log.warn(msg)
        return

    hook = {
        'name': 'web',
        'active': True,
        'config': {
            'url': hook_url,
            'content_type': 'json',
        },
        'events': ['pull_request']
    }
    try:
        repo.create_hook(**hook)
    except:
        message = ("Unable to save webhook. You need to have administration"
                   "privileges over the repository to add webhooks.")
        log.error(message)
        raise
    log.info('Registered hook successfully')


def unregister_hook(repo, hook_url):
    """
    Remove a registered webhook.
    """
    log.info('Removing webhook for %s on %s', hook_url, repo.full_name)
    hooks = repo.hooks()
    hook_id = False
    for hook in hooks:
        if hook.name != 'web':
            continue
        if hook.config['url'] == hook_url:
            hook_id = hook.id
            break

    if not hook_id:
        msg = ("Could not find hook for '%s' "
               "No hooks removed.") % (hook_url)
        log.error(msg)
        raise Exception(msg)
    try:
        repo.hook(hook_id).delete()
    except:
        message = ("Unable to remove webhook. You will need admin "
                   "privileges over the repository to remove webhooks.")
        log.error(message)
        raise
    log.info('Removed hook successfully')


def handle_github_hook():
    event = request.headers.get('X-Github-Event')
    if event == 'ping':
        return Response(status=200)

    try:
        action = request.json["action"]
        pull_request = request.json["pull_request"]
        number = pull_request["number"]
        base_repo_url = pull_request["base"]["repo"]["git_url"]
        head_repo_url = pull_request["head"]["repo"]["git_url"]
        head_repo_ref = pull_request["head"]["ref"]
        user = pull_request["base"]["repo"]["owner"]["login"]
        head_user = pull_request["head"]["repo"]["owner"]["login"]
        repo = pull_request["base"]["repo"]["name"]
        head_repo = pull_request["head"]["repo"]["name"]
    except Exception as e:
        log.error("Got an invalid JSON body. '%s'", e)
        return Response(status=403,
                        response="You must provide a valid JSON body\n")

    log.info("Received GitHub pull request notification for "
             "%s %s, (%s) from: %s",
             base_repo_url, number, action, head_repo_url)

    if action not in ("opened", "synchronize", "reopened", "closed"):
        log.info("Ignored '%s' action." % action)
        return Response(status=204)

    if action == "closed":
        return close_review(user, repo, pull_request)

    gh = get_repository(app.config, head_user, head_repo)
    try:
        lintrc = get_lintrc(gh, head_repo_ref)
        log.debug("lintrc file contents '%s'", lintrc)
    except Exception as e:
        log.warn("Cannot download .lintrc file for '%s', "
                 "skipping lint checks.", base_repo_url)
        log.warn(e)
        return Response(status=204)
    try:
        log.info("Scheduling pull request for %s/%s %s", user, repo, number)
        process_pull_request.delay(user, repo, number, lintrc)
    except:
        log.error('Could not publish job to celery. Make sure its running.')
        return Response(status=500)
    return Response(status=204)
