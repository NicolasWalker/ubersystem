from inspect import getargspec, getmembers, ismethod
from uber.common import *


@all_renderable(*c.API_ACCESS.keys())
class Root:

    def index(self, session, show_revoked=False, message='', **params):
        admin_account = session.current_admin_account()
        api_tokens = session.query(ApiToken)
        if c.ADMIN not in admin_account.access_ints:
            api_tokens = api_tokens.filter_by(admin_account_id=admin_account.id)
        if not show_revoked:
            api_tokens = api_tokens.filter(ApiToken.revoked_time == None)
        api_tokens = api_tokens.options(
            subqueryload(ApiToken.admin_account)
            .subqueryload(AdminAccount.attendee)) \
            .order_by(ApiToken.issued_time).all()
        return {
            'message': message,
            'admin_account': admin_account,
            'api_tokens': api_tokens,
            'show_revoked': show_revoked,
        }

    def reference(self, session):
        from uber.server import jsonrpc_services as jsonrpc
        admin_account = session.current_admin_account()
        services = []
        for name in sorted(jsonrpc.keys()):
            service = jsonrpc[name]
            methods = []
            for method_name, method in getmembers(service, ismethod):
                if not method_name.startswith('_'):
                    method = get_innermost(method)
                    args = getargspec(method).args
                    if 'self' in args:
                        args.remove('self')
                    methods.append({
                        'name': method_name,
                        'doc': method.__doc__,
                        'args': args
                    })
            services.append({
                'name': name,
                'doc': service.__doc__,
                'methods': methods
            })

        return {
            'services': services,
            'admin_account': admin_account
        }

    @ajax
    def create_api_token(self, session, **params):
        if cherrypy.request.method == 'POST':
            params['admin_account_id'] = cherrypy.session['account_id']
            api_token = session.api_token(params)
            message = check(api_token)
            if not message:
                session.add(api_token)
                session.commit()
                return {'result': api_token.id}
            else:
                session.rollback()
                return {'error': message}
        else:
            return {'error': 'POST required'}

    def revoke_api_token(self, session, id=None):
        if not id or not cherrypy.request.method == 'POST':
            raise HTTPRedirect('index')

        api_token = session.api_token(id)
        api_token.revoked_time = datetime.utcnow().replace(tzinfo=pytz.UTC)
        raise HTTPRedirect(
            'index?message={}', 'Successfully revoked API token')
