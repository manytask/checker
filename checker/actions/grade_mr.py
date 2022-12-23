from __future__ import annotations

import re
from datetime import datetime

import gitlab.v4.objects

from ..course import CourseConfig, CourseDriver
from ..course.schedule import CourseSchedule
from ..utils.glab import GitlabConnection
from ..utils.manytask import PushFailedError, push_report
from ..utils.print import print_header_info, print_info

BANNED_FILE_EXTENSIONS = {'csv', 'txt'}
ALLOWED_FILES = ['requirements.txt', 'runtime.txt']
REVIEWED_TAG = 'reviewed'
CHECKLIST_TAG = 'checklist'
BASIC_CHECKLIST_BANNED_TAGS = {CHECKLIST_TAG, REVIEWED_TAG}


def grade_students_mrs_to_master(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        gitlab_connection: GitlabConnection,
        *,
        dry_run: bool = False,
) -> None:
    students_projects = gitlab_connection.get_students_projects(course_config.students_group)
    # for project in students_projects:
    #     full_project: gitlab.v4.objects.Project = GITLAB.projects.get(project.id)
    #     username = full_project.name
    usernames = [project.name for project in students_projects]

    _grade_mrs(
        course_config,
        course_schedule,
        course_driver,
        gitlab_connection,
        usernames,
        dry_run=dry_run,
    )


def grade_student_mrs(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        gitlab_connection: GitlabConnection,
        username: str,
        *,
        dry_run: bool = False,
) -> None:
    _grade_mrs(
        course_config,
        course_schedule,
        course_driver,
        gitlab_connection,
        [username],
        dry_run=dry_run,
    )


def _grade_mrs(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        gitlab_connection: GitlabConnection,
        usernames: list[str],
        *,
        dry_run: bool = False,
) -> None:
    """
    Grade all users from list; to be used with individual and massive MRs check
    """

    # print users to check
    print_info('Users:', usernames, color='orange')

    # get open mrs to filter all users
    students_group = gitlab_connection.get_group(course_config.students_group)
    students_mrs: list[gitlab.v4.objects.GroupMergeRequest] = students_group.mergerequests.list(get_all=True)  # type: ignore
    students_mrs_project_names: set[str] = set()
    for mr in students_mrs:
        students_mrs_project_names.update(mr.web_url.split('/'))
    usernames = [i for i in usernames if i in students_mrs_project_names]
    print_info('Users with MRs:', usernames, color='orange')

    if len(usernames) == 0:
        print_info('Could not find MRs', color='orange')
        return

    # get tasks we need to check
    tag_to_folder = _get_tag_to_folder_dict(course_schedule, course_driver)
    print_info('Tags and folders to check:', tag_to_folder, color='orange')

    # get tutors
    tutors = gitlab_connection.get_all_tutors(course_config.course_group)
    print_info('Tutors:', [f'<{t.username} {t.name}>' for t in tutors], color='orange')
    id_to_tutor = {t.id: t for t in tutors}

    # get current user
    for username in usernames:
        try:
            user = gitlab_connection.get_user_by_username(username)
        except Exception:
            print_info(f'Can not find user with username={username}>', color='orange')
            continue

        user_id = user.id
        print_header_info(f'Current user: <{user.username} {user.name}>')

        # get current user's project
        project = gitlab_connection.get_project_from_group(course_config.students_group, user.username)
        full_project = gitlab_connection.gitlab.projects.get(project.id)
        print_info(f'project {project.path_with_namespace}: {project.web_url}')

        opened_master_mrs = full_project.mergerequests.list(get_all=True, state='opened', target_branch=course_config.default_branch)
        merged_master_mrs = full_project.mergerequests.list(get_all=True, state='merged', target_branch=course_config.default_branch)
        closed_master_mrs = full_project.mergerequests.list(get_all=True, state='closed', target_branch=course_config.default_branch)

        if not opened_master_mrs and not merged_master_mrs and not closed_master_mrs:
            print_info('no open mrs; skip it')
            continue

        print_info(
            f'opened_master_mrs {len(opened_master_mrs)} \t '
            f'merged_master_mrs {len(merged_master_mrs)} \t '
            f'closed_master_mrs {len(closed_master_mrs)}',
            color='grey',
        )

        # Check basic checklist
        print_info('Lookup checklist')
        for mr in opened_master_mrs:  # type: ignore
            print_info(f'Checking MR#{mr.iid} <{mr.title}> ({mr.state})...', color='white')
            print_info(mr.web_url, color='white')
            if mr.title.lower().startswith('wip:') or mr.title.lower().startswith('draft:'):
                print_info('Draft MR - skip it.')
                continue
            _single_mr_check_basic_checklist(
                mr, tag_to_folder, dry_run=dry_run,
            )

        # Check score
        print_info('Lookup score to set')
        for mr in [*opened_master_mrs, *merged_master_mrs, *closed_master_mrs]:
            print_info(f'Checking MR#{mr.iid} <{mr.title}> ({mr.state})...', color='white')
            print_info(mr.web_url, color='white')
            if mr.title.lower().startswith('wip:') or mr.title.lower().startswith('draft:'):
                print_info('Draft MR - skip it.')
                continue
            _singe_mr_grade_score_new(
                course_config, course_schedule, mr, tag_to_folder, id_to_tutor, user_id, dry_run=dry_run,
            )


def _get_tag_to_folder_dict(course_schedule: CourseSchedule, course_driver: CourseDriver) -> dict[str, str]:
    tag_to_folder: dict[str, str] = {}
    for task in course_schedule.get_tasks(enabled=True):
        if task.review:
            source_dir = course_driver.get_task_source_dir(task)
            print_info(f'task "{task.name}" review=true with source_dir={source_dir}', color='grey')
            if source_dir is None:
                print_info('  source_dir is None, skip it', color='grey')
                continue
            tag_to_folder[task.name] = str(source_dir.relative_to(course_driver.root_dir))

    return tag_to_folder


def _singe_mr_grade_score_new(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        mr: gitlab.v4.objects.GroupMergeRequest,
        tag_to_folder: dict[str, str],
        tutors_dict: dict[int, gitlab.v4.objects.GroupMember],
        user_id: int,
        *,
        dry_run: bool = False,
) -> None:
    """
    Get single MR, find or create score discussion and set a score from it
    Looking for comment by tutor under '#### MR score discussion:'
    """
    print_info('labels', mr.labels, color='grey')
    print_info('source_branch', mr.source_branch, color='grey')

    # Search for tags
    tag = None
    for search_tag in tag_to_folder:
        if search_tag in mr.labels:
            tag = search_tag
            break

    if not tag:
        print_info(f'Can not find any of {tag_to_folder.keys()} in MR tags ({mr.labels}). Skip it')
        return

    # get actual task
    task_name = tag_to_folder[tag].split('/')[-1]
    print_info('task_name', task_name, color='grey')
    max_task_score = course_schedule.tasks[task_name].max_score
    print_info('max_task_score', max_task_score, color='grey')

    # Try to find score discussion
    mr_score_discussion = None
    for discussion in mr.discussions.list(get_all=True):
        first_note_id = discussion.attributes['notes'][0]['id']
        first_note = discussion.notes.get(first_note_id)

        if '#### MR score discussion:' in first_note.body:
            mr_score_discussion = discussion
            break
    if not mr_score_discussion:
        mr_score_discussion = mr.discussions.create({
            'body': '\n  '.join([
                '#### MR score discussion:',
                '',
                'After review an examiner will put your score in a response to this discussion',
                f'than he/she will set `{REVIEWED_TAG}` label.',
                '',
                'If the score is not registered in the table, you need to restart the `grade-mr` job',
                '(last score accounted)'
            ])
        })
        try:
            mr_score_discussion.save()
        except Exception:
            print_info('ERROR with saving mr_score_discussion', color='orange')
        mr.save()

    if REVIEWED_TAG not in mr.labels:
        print_info(f'No `{REVIEWED_TAG}` tag. Skip it')
        return

    # get scores
    notes = [
        mr_score_discussion.notes.get(note['id'])
        for note in mr_score_discussion.attributes['notes']
    ]
    notes = notes[1:]

    if not notes:
        print_info('No replays on discussion note. Skip it.', color='grey')
        return

    if 'Score' in notes[-1].body and 'set' in notes[-1].body:
        print_info('Score already set. Skip it.', color='grey')
        return

    score_notes: list[tuple[int, gitlab.v4.objects.ProjectMergeRequestDiscussionNote]] = []
    for note in notes:
        if note.author['id'] not in tutors_dict:
            continue

        try:
            note_score = int(note.body)
        except Exception:
            continue

        if note.updated_at != note.created_at:
            print_info('Note was edited. Please, create a new one! Skip it.', color='grey')
            note.body = note.body + '\n  ' + '*(Note was edited. Please, create a new one! Skip it.)*'
            note.save()
            continue
        score_notes.append((note_score, note))

    if not score_notes:
        print_info('No score replays on discussion note. Skip it.', color='grey')
        return

    # set score from last score
    last_score, last_note = score_notes[-1]

    try:
        if not course_config.manytask_token:
            raise PushFailedError('Unable to find manytask token')

        username, score, _, _, _ = push_report(
            course_config.manytask_url,
            course_config.manytask_token,
            task_name,
            user_id,
            last_score,
            check_deadline=False,
            use_demand_multiplier=False,
        )
        print_info(
            f'Set score for @{username}: {score}',
            color='blue',
        )
        # print_info(f'Submit at {commit_time} (deadline is calculated relative to)', color='grey')
    except PushFailedError:
        raise

    mr_score_discussion.notes.create({'body': f'Score {last_score} set'})
    try:
        mr_score_discussion.save()
    except Exception:
        print_info('ERROR with saving mr_score_discussion', color='orange')
    print_info(f'Score {last_score} set', color='grey')


def _single_mr_check_basic_checklist(
        mr: gitlab.v4.objects.GroupMergeRequest,
        tag_to_folder: dict[str, str],
        *,
        dry_run: bool = False,
) -> None:
    print_info('pipelines', [i.status for i in mr.pipelines.list(get_all=True)], color='grey')
    print_info('labels', mr.labels, color='grey')
    print_info('source_branch', mr.source_branch, color='grey')

    # Search for tags
    tag = None
    for search_tag in tag_to_folder:
        if search_tag in mr.labels:
            tag = search_tag
            break

    if not tag:
        print_info(f'Can not find any of {tag_to_folder.keys()} in MR tags ({mr.labels}). Skip it')
        return

    for banned_tag in BASIC_CHECKLIST_BANNED_TAGS:
        if banned_tag in mr.labels:
            print_info(f'Have `{banned_tag}` tag. Skip it')
            return

    # Check status
    changes = mr.changes()
    is_conflict = mr.has_conflicts or mr.merge_status == 'cannot_be_merged'
    have_no_conflicts = not is_conflict

    # Check pipelines
    if not changes or not changes['head_pipeline']:
        head_pipeline_status = 'failed'
    else:
        head_pipeline_status = changes['head_pipeline']['status']
    pipeline_passed = head_pipeline_status == 'success'

    # changes files
    file_changed: set[str] = set()
    for change in changes['changes']:
        file_changed.update({change['old_path'], change['new_path']})
    print_info('file_changed', file_changed, color='grey')

    # Check single folder or not
    folder_prefix = tag_to_folder[tag]
    print_info('folder_prefix', folder_prefix, color='grey')
    is_single_folder = True
    wrong_folder = None
    for file in file_changed:
        if not file.startswith(folder_prefix):
            # print_info(f'file {file} not startswith {folder_prefix}', color='grey')
            is_single_folder = False
            wrong_folder = file
            break

    # Check extensions
    have_no_additional_files = True
    wrong_file = None
    for file in file_changed:
        if file.split('.')[-1] in BANNED_FILE_EXTENSIONS:
            print_info(f'  check {file}', color='grey')
            for allowed_file in ALLOWED_FILES:
                if file.endswith(allowed_file) or file == allowed_file:
                    print_info(f'  allow {file} as {allowed_file}', color='grey')
                    continue
            have_no_additional_files = False
            wrong_file = file
            break

    # Get Mr checks discussions
    mr_checklist_discussion = None
    mr_checklist_note = None
    for discussion in mr.discussions.list(get_all=True):
        first_note_id = discussion.attributes['notes'][0]['id']
        note = discussion.notes.get(first_note_id)

        if '#### MR checklist (basic checks):' in note.body or '[MR check in progress...]' in note.body:
            mr_checklist_discussion = discussion
            mr_checklist_note = note
            break
    if not mr_checklist_discussion:
        mr_checklist_discussion = mr.discussions.create({'body': '[MR check in progress...]'})
        first_note_id = mr_checklist_discussion.attributes['notes'][0]['id']
        mr_checklist_note = mr_checklist_discussion.notes.get(first_note_id)

    assert mr_checklist_discussion
    assert mr_checklist_note

    # Generate note
    checks_ok = is_single_folder and have_no_additional_files and pipeline_passed and have_no_conflicts
    try:
        _first_try_correct_search = re.search(r'first try correct: (False|True)', mr_checklist_note.body)
        assert _first_try_correct_search
        _first_try_correct_str = _first_try_correct_search.group(0)
        _is_first_try_correct_search = re.search(r'(False|True)', _first_try_correct_str)
        assert _is_first_try_correct_search
        is_first_try_correct = _is_first_try_correct_search.group(0) == 'True'
    except (ValueError, AttributeError, AssertionError):
        is_first_try_correct = checks_ok
    try:
        _updates_num_search = re.search(r'checks num: (\d+)', mr_checklist_note.body)
        assert _updates_num_search
        _updates_num_str = _updates_num_search.group(0)
        current_updates_num_search = re.search(r'(\d+)', _updates_num_str)
        assert current_updates_num_search
        current_updates_num = int(current_updates_num_search.group(0))
    except (ValueError, AttributeError, AssertionError):
        current_updates_num = 0
    now_str = str(datetime.now())
    checklist_note_msg = [
        '#### MR checklist (basic checks):',
        '',
        'Hi! I\'m course bot; I\'m here to check your merge request.',
        'Below you will find a checklist to verify your MR.',
        '',
        f'_first try correct: {is_first_try_correct}_',
        f'_checks num: {current_updates_num + 1}_',
        f'_last check time: {now_str}_',
        '',
        f'- [x] `{tag}` tag exists',
        f'- [{"x" if is_single_folder else " "}] all changes in single folder '
        f'{f"(found {wrong_folder})" if not is_single_folder else ""}',
        f'- [{"x" if have_no_additional_files else " "}] no additional files '
        f'{f"(found {wrong_file})" if not have_no_additional_files else ""}',
        f'- [{"x" if pipeline_passed else " "}] pipeline passed (current status: {head_pipeline_status})',
        f'- [{"x" if have_no_conflicts else " "}] have no merge conflicts',
        '',
    ]

    # TODO: fix it
    if tag == 'cinemabot':
        have_bot_tag = '@' in mr.description
        checks_ok = checks_ok and have_bot_tag
        checklist_note_msg.insert(-1, f'- [{"x" if have_bot_tag else " "}] placed @bot_tag in description')

    # Update MR check discussion
    if checks_ok:
        checklist_note_msg.append('💪 **Ok.** Basic checks have been passed!')
        checklist_note_msg.append('Please, wait for a examiner to check it manually.')
        mr_checklist_discussion.resolved = True
        mr.labels = list({*mr.labels, 'checklist'})
    else:
        checklist_note_msg.append('🔥 **Oops!** There are some errors;')
        checklist_note_msg.append('Please, correct it.')
        mr_checklist_discussion.resolved = False
        mr.labels = list({*mr.labels, 'fix it'})
    # print_info('  \n  '.join(checklist_note_msg))
    mr_checklist_note.body = '  \n'.join(checklist_note_msg)
    mr_checklist_note.save()
    mr_checklist_discussion.save()
    mr.save()

    print_info('Checklist updated')
