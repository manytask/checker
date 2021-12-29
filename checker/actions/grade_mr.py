import re
from datetime import datetime
from typing import Any

from ..utils.repos import GITLAB, MASTER_BRANCH, get_students_projects
from ..utils.print import print_info
from ..course import Course
from .grade import _push_report


BANNED_FILE_EXTENSIONS = {'csv', 'txt'}
REVIEWED_TAG = 'reviewed'
BASIC_CHECKLIST_BANNED_TAGS = {'checklist', REVIEWED_TAG}


def _get_tag_to_folder_dict(course: Course) -> dict[str, str]:
    tag_to_folder: dict[str, str] = {}
    for task in course.get_tasks(enabled=True):
        if task.config.checklist:
            tag_to_folder[task.config.checklist] = str(task.public_dir.relative_to(course.public_dir))

    return tag_to_folder


def grade_score_singe_mr(course: Course, mr, tag_to_folder: dict[str, str], tutors_dict: dict[int , Any], user_id: int) -> None:
    print_info(f'Grading score look up MR {mr.iid} "{mr.title}"...', color='orange')
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

    if REVIEWED_TAG not in mr.labels:
        print_info(f'No `{REVIEWED_TAG}` tag. Skip it')
        return

    task_name = tag_to_folder[tag].split('/')[-1]
    print_info('task_name', task_name, color='grey')
    max_task_score = course.tasks[task_name].max_score
    print_info('max_task_score', max_task_score, color='grey')

    # Get Mr checks discussions
    mr_score_discussion = None
    mr_score_note = None
    for discussion in mr.discussions.list():
        first_note_id = discussion.attributes['notes'][0]['id']
        note = discussion.notes.get(first_note_id)

        # print_info('note.author', note.author, color='grey')
        if 'Your final score is:' in note.body and note.author['id'] in tutors_dict:
            mr_score_discussion = discussion
            mr_score_note = note
            break
    if not mr_score_discussion:
        print_info(f'No score discussions. Skip it.', color='grey')
        return

    if (score_set_search := re.search(r'\(score (\d+) set\)', mr_score_note.body)):
        print_info(f'Found {score_set_search.group(0)}. Skip it.', color='grey')
        return

    if mr_score_note.updated_at != mr_score_note.created_at:
        print_info('Note was edited. Please, create a new one! Skip it.')
        print_info(f'{mr_score_note.updated_at=} {mr_score_note.created_at=}', color='grey')
        return

    try:
        _score_str = re.search(r'Your final score is: (\d+)', mr_score_note.body).group(0)
        score = int(re.search(r'(\d+)', _score_str).group(0))
        # try:
        #     mr_score_discussion.resolved = True
        # except AttributeError:
        #     pass
        mr_score_note.body = _score_str + '  \n' + f'(score {score} setting..)'
        score = min(score, max_task_score * 2)
        print_info(f'(score {score} setting..)')
        mr_score_note.save()
    except (ValueError, AttributeError):
        fixit_str = f'(incorrect score, fixit)  \n' + f'(Please, create a new one with correct score!)'
        mr_score_note.body = mr_score_note.body.replace(fixit_str, '') + fixit_str
        mr_score_note.save()
        return

    # print_info(f'(score {score} setting..)')
    # print_info('user_id', user_id)
    # print_info('task_name', task_name)
    # print_info('max_task_score', max_task_score)

    _push_report(task_name, user_id, score, check_deadline=False)  # TODO: admin flag to set after deadline

    mr_score_note.body = _score_str + '  \n' + f'(score {score} set)'
    mr_score_note.save()


def check_basic_checklist_single_mr(mr, tag_to_folder: dict[str, str]) -> None:
    print_info(f'Checking checklist in MR {mr.iid} "{mr.title}"...', color='orange')
    print_info('pipelines', [i.status for i in mr.pipelines.list()], color='grey')
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
            have_no_additional_files = False
            wrong_file = file
            break

    # Get Mr checks discussions
    mr_checklist_discussion = None
    mr_checklist_note = None
    for discussion in mr.discussions.list():
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

    # Generate note
    checks_ok = is_single_folder and have_no_additional_files and pipeline_passed and have_no_conflicts
    try:
        _first_try_correct_str = re.search(r'first try correct: (False|True)', mr_checklist_note.body).group(0)
        is_first_try_correct = re.search(r'(False|True)', _first_try_correct_str).group(0) == 'True'
    except (ValueError, AttributeError):
        is_first_try_correct = checks_ok
    try:
        _updates_num_str = re.search(r'checks num: (\d+)', mr_checklist_note.body).group(0)
        current_updates_num = int(re.search(r'(\d+)', _updates_num_str).group(0))
    except (ValueError, AttributeError):
        current_updates_num = 0
    now_str = str(datetime.now())
    checklist_note_msg = [
        '#### MR checklist (basic checks):',
        f'_first try correct: {is_first_try_correct}_',
        f'_checks num: {current_updates_num + 1}_',
        f'_last check time: {now_str}_',
        '',
        f'- [x] `{tag}` tag exists',
        f'- [{"x" if is_single_folder else " "}] all changes in single folder {f"(found {wrong_folder})" if not is_single_folder else ""}',
        f'- [{"x" if have_no_additional_files else " "}] no additional files {f"(found {wrong_file})" if not have_no_additional_files else ""}',
        f'- [{"x" if pipeline_passed else " "}] pipeline passed (current status: {head_pipeline_status})',
        f'- [{"x" if have_no_conflicts else " "}] have no merge conflicts',
        '',
    ]

    # TODO: fix it
    if tag == 'cinemabot':
        have_bot_tag = '@' in mr.description
        checklist_note_msg.insert(-1, f'- [{"x" if have_bot_tag else " "}] placed @bot_tag in description')

    # Update MR check discussion
    if checks_ok:
        checklist_note_msg.append('💪 Ok. Basic checks passed!')
        mr_checklist_discussion.resolved = True
        mr.labels = list({*mr.labels, 'checklist'})
    else:
        checklist_note_msg.append('🔥 Please, correct it!')
        mr_checklist_discussion.resolved = False
        mr.labels = list({*mr.labels, 'fix it'})
    # print_info('  \n  '.join(checklist_note_msg))
    mr_checklist_note.body = '  \n'.join(checklist_note_msg)
    mr_checklist_note.save()
    mr_checklist_discussion.save()
    mr.save()


def grade_students_mrs_to_master(course: Course, dry_run: bool = False) -> None:
    tutors = get_all_tutors()
    print_info('Tutors:', [f'<{t.username} {t.name}>' for t in tutors], color='orange')
    tutors_dict = {t.id: t for t in tutors}
    print_info('tutors_dict', {k: v.username for k, v in tutors_dict.items()}, color='grey')

    tag_to_folder = _get_tag_to_folder_dict(course)
    print_info('Tags and folders to check:', tag_to_folder, color='orange')

    students_projects = get_students_projects()

    print_header_info('Lookup students repo')
    for project in students_projects:
        full_project = GITLAB.projects.get(project.id)
        opened_master_mrs = full_project.mergerequests.list(state='opened', target_branch=MASTER_BRANCH)
        merged_master_mrs = full_project.mergerequests.list(state='merged', target_branch=MASTER_BRANCH)

        if not opened_master_mrs and not merged_master_mrs:
            continue

        print_info(f'project {project.path_with_namespace}: {project.web_url}')
        print_info(f'opened_master_mrs {len(opened_master_mrs)} \t merged_master_mrs {len(merged_master_mrs)}', color='grey')

        # Check basic checklist
        for mr in opened_master_mrs:
            check_basic_checklist_single_mr(mr, tag_to_folder)

        # Check score
        full_project = GITLAB.projects.get(project.id)
        project_users_filtered_by_name = full_project.users.list(search=full_project.name)
        project_users_filtered_by_name = [u.id for u in project_users_filtered_by_name]
        if len(project_users_filtered_by_name) == 0:
            return None
        if len(project_users_filtered_by_name) != 1:
            print_info(f'Multiple users in filter {full_project.name}: {project_users_filtered_by_name}', color='orange')
            project_users_filtered_by_name = project_users_filtered_by_name[:1]

        user_id = project_users_filtered_by_name[0]

        for mr in [*opened_master_mrs, *merged_master_mrs]:
            grade_score_singe_mr(course, mr, tag_to_folder, tutors_dict, user_id)
