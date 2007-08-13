from infogami.utils import delegate
import web
from infogami import tdb
import infogami
from infogami.tdb import NotFound
import pickle
from infogami.utils.view import public

def _create_type(site, name, properties=[], description="", is_primitive=False):
    """Quick hack to create a type."""
    def _property(name, type, unique=True, description=""):
        return _get_thing(t, name, tproperty, dict(type=type, unique=unique, description=description))

    ttype = get_type(site, 'type/type')
    tproperty = get_type(site, 'type/property')

    t = _get_thing(site, name, ttype)

    d = {}
    d['is_primitive'] = is_primitive
    d['description'] = description
    d['properties'] = [_property(**p) for p in properties]
    t = new_version(site, name, ttype, d)
    t.save()
    return t

def _get_thing(parent, name, type, d={}):
    try:
        thing = tdb.withName(name, parent)
    except:
        thing = tdb.new(name, parent, type, d)
        thing.save()
    return thing

@infogami.install_hook
def tdbsetup():
    """setup tdb for infogami."""
    from infogami import config
    # hack to disable tdb hooks
    tdb.tdb.hooks = []
    tdb.setup()


    site = _get_thing(tdb.root, config.site, tdb.root)
    from infogami.utils.context import context
    context.site = site 
    
    # type is created with tdb.root as type first and later its type is changed to itself.
    ttype = _get_thing(site, "type/type", tdb.root)
    tproperty = _get_thing(site, "type/property", ttype)

    tint = _create_type(site, "type/int", is_primitive=True)
    tboolean = _create_type(site, "type/boolean", is_primitive=True)
    tstring = _create_type(site, "type/string", is_primitive=True)
    ttext = _create_type(site, "type/text", is_primitive=True)
    
    tproperty = _create_type(site, "type/property", [
       dict(name='type', type=ttype),
       dict(name='unique', type=tboolean),
       dict(name='description', type=ttext),
    ])
    
    tbackreference = _create_type(site, 'type/backreference', [
        dict(name='type', type=ttype),
        dict(name='property_name', type=tstring),
    ])

    ttype = _create_type(site, "type/type", [
       dict(name='description', type=ttext, unique=True),
       dict(name='is_primitive', type=tboolean, unique=True),
       dict(name='properties', type=tproperty, unique=False),
       dict(name='backreferences', type=tbackreference, unique=False),
    ])

    _create_type(site, 'type/page', [
        dict(name='title', type=tstring), 
        dict(name='body', type=ttext)])
        
    _create_type(site, 'type/user', [
        dict(name='emaiil', type=tstring), 
        dict(name='displayname', type=tstring)])
        
    _create_type(site, 'type/delete', [])

    # for internal use
    _create_type(site, 'type/thing', [])

class ValidationException(Exception): pass

def get_version(site, path, revision=None):
    return tdb.withName(path, site, revision=revision and int(revision))

def new_version(site, path, type, data):
    if site.id:
        try:
            #@@ Explain this later
            p = tdb.withName(path, site)
            p.type = type
            p.setdata(data)
            return p
        except tdb.NotFound:
            pass
                
    return tdb.new(path, site, type, data)
    
def get_user(site, userid):
    try:
        u = tdb.withID(userid)
        if u.type == get_type(site, 'type/user'):
            return u
    except NotFound:
        return None

def get_user_by_name(site, username):
    try:
        return tdb.withName('user/' + username, site)
    except NotFound:
        return None
    
def new_user(site, username, email):
    d = dict(email=email)
    return tdb.new('user/' + username, site, get_type(site, "type/user"), d)

def get_password(user):
    return db.get_user_preferences(user).d.get('password')

def get_user_preferences(user):
    try:
        return tdb.withName('preferences', user)
    except NotFound:
        site = user.parent
        type = get_type(site, 'type/thing')
        return tdb.new('preferences', user, type)
    
@public
def get_type(site, name):
    return tdb.withName(name, site)

def new_type(site, name, data):
    try:
        return get_type(site, name)
    except tdb.NotFound:
        t = tdb.new(name, site, get_type(site, 'type/type'), data)
        t.save()
        return t

def get_site(name):
    return tdb.withName(name, tdb.root)

@public
def get_recent_changes(site, author=None, limit=None):
    if author:
        return tdb.Versions(parent=site, author=author, limit=limit)
    else:
        return tdb.Versions(parent=site, limit=limit)

@public
def list_pages(site, path):
    """Lists all pages with name path/*"""
    delete = get_type(site, 'type/delete')
    
    if path == "":
        pattern = '%'
    else:
        pattern = path + '/%'
        
    return web.query("""SELECT t.id, t.name FROM thing t 
            JOIN version ON version.revision = t.latest_revision AND version.thing_id = t.id
            JOIN datum ON datum.version_id = version.id 
            WHERE t.parent_id=$site.id AND t.name LIKE $pattern 
            AND datum.key = '__type__' AND datum.value != $delete.id
            ORDER BY t.name LIMIT 100""", vars=locals())
                   
def get_site_permissions(site):
    if hasattr(site, 'permissions'):
        return pickle.loads(site.permissions)
    else:
        return [('/.*', [('everyone', 'view,edit')])]
    
def set_site_permissions(site, permissions):
    site.permissions = pickle.dumps(permissions)
    site.save()
