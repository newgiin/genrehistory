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
            template = JINJA_ENVIRONMENT.get_template(
                'templates/history.html')
            self.response.write(template.render(template_values))
        else:
            self.redirect('/', permanent=True)

app = webapp2.WSGIApplication([('/history', MainPage)], debug=True)
