
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.urls import reverse
from django.views import generic

from .models import Course, Enrollment, Question, Choice, Submission


def registration_request(request):
    context = {}

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        if User.objects.filter(username=username).exists():
            context['message'] = "User already exists."
        else:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")

    return render(
        request,
        'onlinecourse/user_registration_bootstrap.html',
        context
    )


def login_request(request):
    context = {}

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."

    return render(
        request,
        'onlinecourse/user_login_bootstrap.html',
        context
    )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    if user.is_authenticated:
        return Enrollment.objects.filter(
            user=user,
            course=course
        ).exists()
    return False


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if not user.is_authenticated:
        return redirect('onlinecourse:login')

    if not check_if_enrolled(user, course):
        Enrollment.objects.create(
            user=user,
            course=course,
            mode='honor'
        )

        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


# TASK 5 - EXTRACT ANSWERS

def extract_answers(request):
    selected_answers = []

    for key, value in request.POST.items():
        if key.startswith('choice_'):
            try:
                selected_answers.append(int(value))
            except (ValueError, TypeError):
                continue

    return selected_answers


# TASK 5 - SUBMIT EXAM

def submit(request, course_id):

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    if request.method != 'POST':
        return redirect('onlinecourse:course_details', pk=course_id)

    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    selected_ids = extract_answers(request)

    selected_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    submission.choices.set(selected_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


# TASK 5 - EVALUATE EXAM

def show_exam_result(request, course_id, submission_id):

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    selected_choices = submission.choices.all()

    selected_ids = set(
        selected_choices.values_list('id', flat=True)
    )

    questions = Question.objects.filter(
        course=course
    ).prefetch_related('choice_set')

    total_points = 0
    earned_points = 0
    question_results = []

    for question in questions:

        total_points += question.grade

        choices = list(question.choice_set.all())

        question_selected_ids = [
            choice.id
            for choice in choices
            if choice.id in selected_ids
        ]

        is_correct = question.is_get_score(
            question_selected_ids
        )

        if is_correct:
            earned_points += question.grade

        question_results.append({
            'question': question,
            'is_correct': is_correct,
            'points_awarded': question.grade if is_correct else 0,
            'selected_choices': [
                choice for choice in choices
                if choice.id in selected_ids
            ],
            'correct_choices': [
                choice for choice in choices
                if choice.is_correct
            ]
        })

    if total_points > 0:
        grade = round(
            (earned_points / total_points) * 100,
            2
        )
    else:
        grade = 0

    context = {
        'course': course,
        'submission': submission,
        'choices': selected_choices,
        'selected_ids': selected_ids,
        'questions': questions,
        'question_results': question_results,
        'score': earned_points,
        'total_points': total_points,
        'grade': grade,
        'passed': grade > 80
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
