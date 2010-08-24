from django.conf.urls.defaults import patterns, url, include

from quanda.feeds import RssQuestions, RssAnswers

feeds = {
    'latest': RssQuestions,
    'answers': RssAnswers,
}

urlpatterns = patterns('quanda.views',
    url(r'^$', 'index', name='quanda_index'),
    
    url(r'^search/$', 'search', name='quanda_search'),
    
    url(r'^profile/(?P<username>\w+)/$', 'profile', name='quanda_public_profile'),
    
    url(r'^ask/$', 'question_create_edit', name='quanda_question_create'),
    url(r'^(?P<question_id>\d+)/edit/$', 'question_create_edit', name='quanda_question_edit'),
    url(r'^(?P<question_id>\d+)/voteup/$', 'voting.question_adjust_vote', kwargs={'delta': 1}, name='quanda_question_vote_up'),
    url(r'^(?P<question_id>\d+)/votedown/$', 'voting.question_adjust_vote', kwargs={'delta': -1}, name='quanda_question_vote_down'),
    url(r'^(?P<question_id>\d+)/record_view/$', 'record_view', name='quanda_record_view'),
    url(r'^(?P<question_id>\d+)/', 'question_read', {'msg':'test'}, name='quanda_question_read'),
    
    url(r'^lists/$', 'lists', name='quanda_lists'),
    url(r'^lists/(?P<list_id>\d+)/$', 'list_details', name='quanda_list_details'),

    url(r'^answers/(?P<answer_id>\d+)/edit/$', 'answer_edit', name='quanda_answer_edit'),
    url(r'^answers/(?P<answer_id>\d+)/pick/$', 'pick_answer', name='quanda_pick_answer'),
    url(r'^answers/(?P<answer_id>\d+)/voteup/$', 'voting.answer_adjust_vote', kwargs={'delta': 1}, name='quanda_answer_vote_up'),
    url(r'^answers/(?P<answer_id>\d+)/votedown/$', 'voting.answer_adjust_vote', kwargs={'delta': -1}, name='quanda_answer_vote_down'),
    
    url(r'^tags/admin/$', 'tags_admin', name='quanda_tags_admin'),
    url(r'^tags/admin/(?P<tag_id>\d+)/delete/$', 'delete_tag', name='quanda_delete_tag'),
    url(r'^tags/(?P<tag_id>\w+)/$', 'view_tag', name='quanda_view_tag'),
        
    (r'^install/$', 'install'),
    (r'^api/', include('quanda.api.urls')),
    
)

urlpatterns += patterns('django.contrib.syndication.views',
    url(r'^feeds/(?P<url>.*)/$', 'feed', {'feed_dict': feeds}, name='quanda_feed'),
)