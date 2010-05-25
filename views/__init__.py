import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

import quanda.models
from quanda.forms import QuestionForm, QuestionTagForm, QuestionListForm, QuestionListOrderForm, QuestionListAddForm, AnswerForm, CommentForm
from quanda.models import Question, QuestionVote, QuestionTag, QuestionList, QuestionListOrder, QuestionView, Answer, AnswerVote, Comment
from quanda.utils import get_user_rep
from profile.models import Profile
from profile.forms import ProfileForm, RepForm

TINY_MCE_JS_LOCATION = getattr(settings, 'TINY_MCE_JS_LOCATION', 'http://teebes.com/static/js/tiny_mce/tiny_mce.js')

# === Index, Tags, Search & Profile ===
def index(request):    
    if request.user.is_authenticated():
        your_answers = Answer.objects.filter(question__author=request.user).order_by("-posted")[:5]
    else:
        your_answers = None
    
    try:    
        featured = QuestionList.objects.get(title='featured').questions.all().order_by('questionlistorder__order')
    except QuestionList.DoesNotExist:
        featured = None

    return render_to_response('quanda/index.html', {
        'featured': featured,
        'top_questions': Question.objects.annotate(score=Sum('questionvotes__score')).order_by('-score')[:5],
        'recent_questions': Question.objects.order_by("-posted")[:5],
        'your_answers': your_answers,
        'unanswered_questions': Question.objects.filter(answers__isnull=True).order_by('-posted')[:5],
        }, context_instance=RequestContext(request))

def search(request):
    """
    At this time this search view doesn't even deserve the name. Need to
    identify an existing search package and use it here.
    """
    query = ''
    if request.method == 'GET':
        query = request.GET['query']
    
    if query == '': # if nothing is passed, return the 50 most recent questions
        results = Question.objects.all().order_by('-posted')[:50]
    else:
        tags = QuestionTag.objects.values_list('title', flat=True)
        present_tags = []
        for word in query.split(' '):
            if word in tags:
                present_tags.append(word)
    
        results = Question.objects.filter(tags__title__in=present_tags).distinct().order_by('-posted')

    return render_to_response("quanda/search_results.html", {
        'results': results,
        }, context_instance=RequestContext(request))
    return HttpResponse("search")

def profile(request, username):
    
    user = get_object_or_404(User, username=username)
#    profile = Profile.objects.get_or_create(user=user)[0]
    profile = user.get_profile()

    if request.method == 'POST':
        if request.POST.has_key('change_rep'):
            if not request.user.is_staff:
                return HttpRepsonse("Unauthorized")
            rep_form = RepForm(request.POST)
            if rep_form.is_valid():
                profile.reputation = rep_form.cleaned_data['base_rep']
                profile.save()
                return HttpResponseRedirect(reverse('quanda_public_profile', args=[username]))
        elif request.POST.has_key('save_profile'):
            if not request.user == profile.user:
                return HttpResponse("Unauthorized")
            profile_form = ProfileForm(request.POST, instance=profile)
            if profile_form.is_valid():
                #return HttpResponse("ready to save")
                profile = profile_form.save()
                return HttpResponseRedirect(reverse('quanda_public_profile', args=[username]))
    else:
        profile_form = ProfileForm(instance=profile)
        rep_form = RepForm(initial={'base_rep': profile.reputation})
    
    return render_to_response("quanda/profile.html", {
        'rep_form': rep_form,
        'profile_form': profile_form,
        'questions': Question.objects.filter(author__username=username).order_by('-posted'),
        'answers': Answer.objects.filter(author__username=username).order_by('-posted'),
        'profile': profile,
        'tinymce': TINY_MCE_JS_LOCATION,
        }, context_instance=RequestContext(request))


def view_tag(request, tag_id):
    return render_to_response("quanda/search_results.html", {
        'results': QuestionTag.objects.get(pk=tag_id).questions.order_by('-posted'),
        }, context_instance=RequestContext(request))
    return HttpResponse("This is tag %s" % tag_id)

# === Questions & Answers ===
def question_create_edit(request, question_id=None):
    try:
        question = Question.objects.get(pk=question_id)
        if not request.user.is_authenticated() or request.user.username != question.author.username:
            return HttpResponse("You are not allowed to edit this post.")
    except Question.DoesNotExist:
        question = None
        
    if request.method == 'POST':
        form = QuestionForm(request.user, request.POST, instance=question)
        if form.is_valid():
            question = form.save()
            return HttpResponseRedirect(reverse('quanda_question_read', args=[question.id]))
    else:        
        tags = []
        if question:
            tags = question.tags.values_list('id', flat=True)
        form = QuestionForm(request.user, instance=question, initial={'tags': tags})
    
    return render_to_response('quanda/question_create_edit.html', {
        'form': form,
        'tinymce': TINY_MCE_JS_LOCATION,
        }, context_instance=RequestContext(request))

    
def question_read(request, question_id=None, msg=None, context={}):
    question = get_object_or_404(Question, pk=question_id)
    
    # user answers question
    answer_form = AnswerForm(request.user, question)    
    if request.method == "POST" and request.POST.has_key('answer_question'):
        answer_form = AnswerForm(request.user, question, request.POST)
        if answer_form.is_valid():
            answer = answer_form.save()
            return HttpResponseRedirect(reverse('quanda_question_read', args=[question_id]))
    
    # ==== comments ====
    if request.method == "POST" and request.POST.has_key('comment'):
        # in order to leave a comment, one must be logged in & be the
        # author of the question or have more rep than the configurable
        # requirement to leave comments        
        if request.user.is_authenticated():
            required_rep = getattr(settings, 'LEAVE_COMMENT', 0)
            if get_user_rep(request.user.username) >= required_rep:
                comment_form = CommentForm(request.POST)
                if comment_form.is_valid():
                    # create the comment and redirect         
                    comment = Comment(
                        content_object = getattr(
                            quanda.models,
                            comment_form.cleaned_data['content_type'],
                            ).objects.get(pk=comment_form.cleaned_data['object_id']),
                        comment_text = comment_form.cleaned_data['comment_text'],
                        posted = datetime.datetime.now(),
                        user = request.user,
                        ip = request.META['REMOTE_ADDR'],
                    )
                    comment.save()
                    return HttpResponseRedirect(reverse('quanda_question_read', args=[question_id]))
            else:
                context['msg'] = "You must have at least %s reputation in order to leave comments " % required_rep
        else:
            context['msg'] = "You must be logged in to comment"

    # get how the user previously voted on this question
    try:
        user_question_previous_vote = QuestionVote.objects.get(question=question, user=request.user).score
    except Exception:
        user_question_previous_vote = 0

    # get questions related to this one
    related_questions = Question.objects\
                        .filter(tags__id__in=question.tags.all())\
                        .exclude(pk=question.id)\
                        .distinct()\
                        .order_by('-posted')

    answers_q = Answer.objects\
                .filter(question=question)\
                .annotate(score=Sum('answervotes__score'))\
                .order_by('-posted')\
                .order_by('-score')\
                .order_by('-user_chosen')    

    user_answered_question = False # whether this user answered the question    
    answers = []
    for answer in answers_q:
        # did the user answer the question?
        if answer.author == request.user:
            user_answered_question = True
        
        # indicates the user's last vote on this answer
        try:
            answer_vote = AnswerVote.objects.get(answer=answer, user=request.user).score
        except Exception:
            answer_vote = 0
        answer.user_prev_vote = answer_vote
        
        answer.comment_form = CommentForm(initial={'content_type': 'Answer', 'object_id': answer.id})        
        
        answers.append(answer)

    # add comment form to the question
    question.comment_form = CommentForm(initial={'content_type': 'Question', 'object_id': question.id})

    context['question'] = question
    context['user_question_previous_vote'] = user_question_previous_vote
    context['related_questions'] = related_questions
    context['answer_form'] = answer_form
    context['answers'] = answers
    context['user_answered_question'] = user_answered_question
    context['tinymce'] = TINY_MCE_JS_LOCATION

    return render_to_response('quanda/question_read.html',
                               context,
                               context_instance=RequestContext(request))

def record_view(request, question_id):
    """
    Keep track of a question's view count.
    In order to keep as accurate as possible, session keys are checked
    This view should preferably be called either via Ajax or as a stylesheet
    to help avoid search engines polluting the view count
    """

    question = get_object_or_404(Question, pk=question_id)

    if not QuestionView.objects.filter(
                    question=question,
                    session=request.session.session_key):
        view = QuestionView(question=question,
                            ip=request.META['REMOTE_ADDR'],
                            created=datetime.datetime.now(),
                            session=request.session.session_key)
        view.save()
    
    return HttpResponse(u"%s" % QuestionView.objects.filter(question=question).count())

@login_required
def pick_answer(request, answer_id=None):
    try:
        answer = Answer.objects.get(pk=answer_id)
    except Answer.DoesNotExist:
        raise Http404
    
    if answer.question.author != request.user:
        return HttpResponse("This is not your question to answer")
    
    try:
        already_chosen = Answer.objects.get(question=answer.question, user_chosen=True)
        already_chosen.user_chosen = False
        already_chosen.save()
    except Answer.DoesNotExist: pass

    answer.user_chosen = True
    answer.save()
    
    return HttpResponseRedirect(reverse('quanda_question_read', args=[answer.question.id]))

@login_required
def answer_edit(request, answer_id=None):
    answer = get_object_or_404(Answer, pk=answer_id)
    
    if request.user != answer.author:
        return HttpResponse("Unauthorized")
    
    if request.method == 'POST':
        answer_form = AnswerForm(request.user, answer.question, request.POST, edit=True, instance=answer)
        if answer_form.is_valid():
            answer_form.save()
            return HttpResponseRedirect(reverse('quanda_question_read', args=[answer.question.id]))
    else:
        answer_form = AnswerForm(request.user, answer.question, instance=answer)
    
    return render_to_response("quanda/answer_edit.html", {
        'answer_form': answer_form,
        'answer': answer,
        'tinymce': TINY_MCE_JS_LOCATION,
    }, context_instance=RequestContext(request))
    
    return HttpResponse('edit')

# === Staff zone === 
@login_required
def tags_admin(request):
    if not request.user.is_staff: return HttpResponse("Unauthorized")    
    if request.method == 'POST':
        new_tag_form = QuestionTagForm(request.POST)
        if new_tag_form.is_valid():
            new_tag = new_tag_form.save()
            return HttpResponseRedirect(reverse('quanda_tags_admin'))
    else:
        new_tag_form = QuestionTagForm()
    
    return render_to_response("quanda/tags_admin.html", {
        'tags': QuestionTag.objects.all(),
        'new_tag_form': new_tag_form,
        }, context_instance=RequestContext(request))
    
@login_required
def delete_tag(request, tag_id):
    if not request.user.is_staff: return HttpResponse("Unauthorized")
    tag = get_object_or_404(QuestionTag, pk=tag_id)
    tag.delete()
    return HttpResponseRedirect(reverse('quanda_tags_admin'))

@login_required
def lists(request):
    if not request.user.is_staff: return HttpResponse("Unauthorized")
    if request.method == 'POST':
        form = QuestionListForm(request.POST)
        if form.is_valid():
            list = form.save()
            return HttpResponseRedirect(reverse('quanda_lists'))
    else:
        form = QuestionListForm()
    return render_to_response("quanda/lists.html", {
        'form': form,
        'lists': QuestionList.objects.all(),
    }, context_instance=RequestContext(request))
    
@login_required
def list_details(request, list_id):
    if not request.user.is_staff: return HttpResponse("Unauthorized")
    
    list = QuestionList.objects.get(pk=list_id)
    questions_list = QuestionListOrder.objects.filter(question_list=list).order_by('order')

    edit_form = QuestionListForm(instance=list)
    add_question_form = QuestionListAddForm(list)
    invalid_count = False
    if request.method == "POST":
        
        if request.POST.has_key('edit_list'):
            edit_form = QuestionListForm(request.POST, instance=list)
            if edit_form.is_valid():
                list = edit_form.save()
                return HttpResponseRedirect(reverse('quanda_list_details', args=[list.id]))

        elif request.POST.has_key('reorder'):
            for value in request.POST.values():
                if value != '0' and request.POST.values().count(value) > 1:
                    invalid_count = True
                    break
            if not invalid_count:
                for k, v in request.POST.items():
                    if k != 'reorder':
                        list_item = questions_list.get(question__id=k)
                        if v == '0':
                            list_item.delete()
                        else:
                            list_item.order = v
                            list_item.save()
                return HttpResponseRedirect(reverse('quanda_list_details', args=[list.id]))

        elif request.POST.has_key('add_question'):
            add_question_form = QuestionListAddForm(list, request.POST)
            if add_question_form.is_valid():
                question = get_object_or_404(Question, pk=add_question_form.cleaned_data['question'])            
                list_questions = QuestionListOrder.objects.filter(question_list=list)
                if not list_questions:
                    new_item = QuestionListOrder(question_list=list, question=question, order=1)
                    new_item.save()
                    return HttpResponseRedirect(reverse('quanda_list_details', args=[list.id]))
                else:
                    order_number = list_questions.order_by('-order')[0].order + 1
                    new_item = QuestionListOrder(question_list=list, question=question, order=order_number)
                    new_item.save()
                    return HttpResponseRedirect(reverse('quanda_list_details', args=[list.id]))

    return render_to_response("quanda/list_details.html", {
        'list': list,
        'edit_form': edit_form,
        'add_question_form': add_question_form,
        'questions_list': questions_list,
        'invalid_count': invalid_count,
    }, context_instance=RequestContext(request))

@login_required
def install(request):
    """
    This view is a utility that makes sure that the objects that quanda
    needs on the db side are there. It should always check to see if the data
    is already there as the view can always be run after it's already been run.
    """
    
    if not request.user.is_staff: return HttpResponse("Unauthorized")
    
    # if a user named 'anonymous_user' does not exist, create it
    if not User.objects.filter(username='anonymous_user'):
        anonymous_user = User(username='anonymous_user')
        anonymous_user.save()
        
    # go through every ever and create a profile object if it doesn't already
    # exist. Also, give them each admin 10000 initial rep points
    for user in User.objects.all():
        profile = Profile.objects.get_or_create(user=user)[0]
        if user.is_staff:
            if profile.reputation < 1000:
                profile.reputation = 1000
                profile.save()
    
    return HttpResponse("done")