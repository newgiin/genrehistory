import webapp2
import os
import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
        extensions=['jinja2.ext.autoescape'])

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = self.request.get('user')

        if user:
            template_values = {'user':user}
            if self.request.get('tp') is not None:
                template_values['tp'] = self.request.get('tp')
            template = JINJA_ENVIRONMENT.get_template(
                'templates/tag_graph.html')
            self.response.write(template.render(template_values))
        else:
            self.redirect('/', permanent=True)

app = webapp2.WSGIApplication([('/tag_graph', MainPage)], debug=True)
