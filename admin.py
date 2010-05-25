from django.contrib import admin
from quanda.models import Question, QuestionTag, Answer

class QuestionAdmin(admin.ModelAdmin): pass
class AnswerAdmin(admin.ModelAdmin): pass
class QuestionTagAdmin(admin.ModelAdmin): pass

admin.site.register(Question, QuestionAdmin)
admin.site.register(Answer, AnswerAdmin)
admin.site.register(QuestionTag, QuestionTagAdmin)
