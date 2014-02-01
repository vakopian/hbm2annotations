from lxml.html.diff import copy_annotations
from bs4 import BeautifulSoup
import re, sys, os

classes = {}
all_class_paths = {}
embeddable_classes = {}

def uc_first(s):
    if not s:
        return s
    return s[0].upper() + s[1:]


def lc_first(s):
    if not s:
        return s
    return s[0].lower() + s[1:]


def inverse_key_column_to_property(inverse_key_column):
    if inverse_key_column[-2:].lower() == 'id':
        return lc_first(inverse_key_column[0:-2])
    return lc_first(inverse_key_column)


class JavaAnn:
    def __init__(self, ann, params=None, target_class=None):
        self.name = ann
        self.target_class = target_class
        if params:
            if isinstance(params, basestring):
                self.params = [params]
            self.params = params

    def __str__(self):
        if self.params:
            return self.name + "(" + ", ".join(self.params) + ")"
        return self.name

class JavaSource:
    def __init__(self, java_file_path):
        self.java_file_path = java_file_path
        self.cls_short_name = os.path.splitext(os.path.basename(java_file_path))[0]
        self.annotated_props = {}
        self.prop_annotations = {}
        self.class_annotations = []
        self.imports = []
        with open(java_file_path) as java_file:
            self.src = java_file.read()
            self.src = self.src.replace('\r', '')
            self.src = self.src.replace(' * To change this template use File | Settings | File Templates.\n', '')
            self.properties = [lc_first(m.group(1)) for m in re.finditer(r'^\n*\s*(?:public|protected|private)\s+\b\w+(?:<\s*[\w, ]+\s*>)?\s*(?:get|is)(\w+)\s*\(\s*\)', self.src, flags=re.MULTILINE)]
            self.superclass = None
            m = re.search(r'^\n*\s*public\s+class\s+' + self.cls_short_name + r'\s+extends\s+(\w+)', self.src, flags=re.MULTILINE)
            if m:
                self.superclass = JavaSource(all_class_paths[m.group(1)])

    def has_property(self, prop):
        return prop in self.properties

    def add_property_annotation(self, prop, annotation):
        if not isinstance(annotation, JavaAnn):
            raise Exception("annotation must be JavaAnn object")
        if prop not in self.prop_annotations:
            self.prop_annotations[prop] = [annotation]
        else:
            self.prop_annotations[prop].append(annotation)

    def find_scheduled(self, ann_name, target_class='ANY'):
        res = []
        for prop, annotations in self.prop_annotations:
            for ann in annotations:
                if ann.name == ann_name and ((target_class == 'ANY' and ann.target_class) or (target_class and ann.target_class == target_class)):
                    res.append((prop, ann))
        return res

    def _do_add_property_annotation(self, prop, annotation):
        if not prop:
            raise Exception('property must not be empty')
        if not annotation:
            raise Exception('annotation must not be empty')
        if self.has_property(prop):
            self.src = re.sub(r'^(\n*)(\s*)((?:public|protected|private)\s+\b\w+(?:<\s*[\w, ]+\s*>)?\s*(?:get|is)' + uc_first(prop) + r'\s*\(\s*\))', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags=re.MULTILINE)
            self.mark_as_mapped(prop)
        elif self.superclass:
            self.superclass.add_property_annotation(prop, annotation)
            #todo: may need a @MappedSuperclass annotation
        else:
            raise Exception('could not find property ' + prop + ' in class ' + self.cls_short_name)

    def mark_as_mapped(self, prop):
        self.annotated_props[prop] = prop

    def find_property_type(self, prop):
        if not prop:
            raise Exception('property must not be empty')
        m = re.search(r'^\n*\s*(?:public|protected|private)\s+\b(\w+)(?:<\s*[\w, ]+\s*>)?\s*(?:get|is)' + uc_first(prop) + r'\s*\(\s*\)', self.src, flags=re.MULTILINE)
        return m.group(1)

    def add_class_annotation(self, annotation):
        self.class_annotations.append(annotation)

    def _do_add_class_annotation(self, annotation):
        self.src = re.sub(r'^(\n*)(\s*)(public\s+class\s+' + self.cls_short_name + ')', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags=re.MULTILINE)

    def add_import(self, imprt):
        self.imports.append(imprt)

    def _do_add_import(self, imprt):
        self.src = re.sub(r'^(package\s+[\w\.]+;)' + "\n", r'\1' + '\n\nimport ' + imprt + ";\n", self.src, 1, flags=re.MULTILINE)

    def write(self):
        for imprt in self.imports:
            self._do_add_import(imprt)

        for ann in self.class_annotations:
            self._do_add_class_annotation(ann)

        for (prop, annotations) in self.prop_annotations:
            for ann in annotations:
                self._do_add_property_annotation(prop, ann)

        self.add_transient_annotations()
        with open(self.java_file_path, 'w') as java_file:
            java_file.write(self.src)

    def get_property_annotations(self, prop):
        ann = []
        for m in re.finditer(r'^((?:\n*\s*@\w+(?:\(.*\n)?\n*)+)\s*(?:public|protected|private)\s+\b\w+(?:<\s*[\w, ]+\s*>)?\s*(?:get|is)' + uc_first(prop) + r'\s*\(\s*\)', self.src, flags=re.MULTILINE):
            ann += m.group(1).split()
        #print '.........................property', prop, 'is annotated with', ann
        return ann

    def add_transient_annotations(self):
        for prop in self.properties:
            if prop not in self.annotated_props:
                annotations = self.get_property_annotations(prop)
                if '@Transient' not in annotations and '@OneToOne' not in annotations and '@ManyToOne' not in annotations and '@OneToMany' not in annotations:
                    self.add_property_annotation(prop, JavaAnn('@Transient'))


def collection_field(src, collection, many_to_many=False):
    args = []
    join_table_args = []
    name = collection.get('name')
    if not name:
        raise Exception('BAD tag ' + str(collection))
    lazy = collection.get('lazy')
    fetch = collection.get('fetch')
    outer_join = collection.get('outer-join')
    table = collection.get('table')
    if lazy == 'false' or fetch == 'join':
        args.append('fetch = FetchType.EAGER')
    elif lazy is not None or outer_join != 'true':
        args.append('fetch = FetchType.LAZY')

    key_column = None
    not_null = None
    key = collection.find('key')
    if key:
        key_column = key.get('column')
        if not key_column:
            kc = key.find('column')
            if kc:
                key_column = kc['name']
                not_null = kc.get('not-null')

    if key_column:
        not_null_arg = ''
        if not_null == 'true':
            not_null_arg = ', nullable = false'
        join_table_args.append('joinColumns = {@JoinColumn(name = "' + key_column + '"' + not_null_arg + ')}')

    idx = collection.find('index')
    if not idx:
        idx = collection.find('list-index')
    if idx and idx.get('column'):
        src.add_property_annotation(name, JavaAnn('@OrderColumn', 'name = "' + idx.get('column') + '"'))

    map_key = collection.find('map-key')
    if map_key:
        if map_key.get('column'):
            src.add_property_annotation(name, JavaAnn('@MapKeyColumn', 'name = "' + map_key.get('column') + '"'))
        if map_key.get('formula'):
            src.add_property_annotation(name, JavaAnn('@MapKey', 'name = "' + map_key.get('formula') + '"'))

    target_class = None
    rel = collection.find('many-to-many')
    if rel:
        many_to_many = (rel.get('unique') != 'true')
        inverse_join_column = rel.get('column')
        if inverse_join_column:
            join_table_args.append('inverseJoinColumns = {@JoinColumn(name = "' + inverse_join_column + '")}')
    else:
        rel = collection.find('one-to-many')
        if rel:
            many_to_many = False
            target_class = rel.get('class')

    if table:
        join_table_args.append('name = "' + table + '"')

    cascade = collection.get('cascade')
    if cascade:
        if cascade == 'all':
            args.append('cascade = CascadeType.ALL')
            pass
        elif cascade == 'merge':
            args.append('cascade = CascadeType.MERGE')
            pass
        elif cascade == 'all-delete-orphan':
            args.append('cascade = CascadeType.ALL')
            if not many_to_many:
                args.append('orphanRemoval = true')
            pass
        elif cascade == 'delete-orphan':
            if not many_to_many:
                args.append('orphanRemoval = true')
            pass
        else:
            raise Exception('cascade type [' + cascade + '] not handled')
    inverse = collection.get('inverse')
    mapped_by = inverse == 'true'
    if mapped_by:
        if not key_column:
            raise Exception('BAD ' + str(key))
        mapped_by_prop = inverse_key_column_to_property(key_column)
        args.append('mappedBy = "' + mapped_by_prop + '"')

    order_by = collection.get('order-by')
    if order_by:
        src.add_property_annotation(name, JavaAnn('@OrderBy', '"' + order_by + '"'))

    if join_table_args and not mapped_by:
        src.add_property_annotation(name, JavaAnn('@JoinTable', join_table_args))

    if many_to_many:
        ann = '@ManyToMany'
    else:
        ann = '@OneToMany'

    if args:
        src.add_property_annotation(name, JavaAnn(ann, args, target_class))
    else:
        src.add_property_annotation(name, JavaAnn(ann, None, target_class))


def process_hbm(hbm, java_src_base):
    with open(hbm) as hbm_file:
        soup = BeautifulSoup(hbm_file, 'xml')
        for cls in soup.find('hibernate-mapping').find_all('class', recursive=False):
            cls_name = cls.get('name')
            classes[cls_name] = {}
            cls_short_name = cls_name.split('.')[-1]
            table = cls.get('table')
            java_file_path = java_src_base + '/' + cls_name.replace('.', '/') + '.java'
            if not os.path.exists(java_file_path):
                print 'skipping class', cls_name, 'corresponding java file', java_file_path, 'does not exist'
                continue

            print 'processing class', cls_short_name, '...',
            src = JavaSource(java_file_path)

            src.add_import('javax.persistence.*')
            unique_args = []
            src.add_class_annotation('@Entity')

            # primary key
            for id_tag in cls.find_all('id', recursive=False):
                name = id_tag.get('name')
                if name == 'id':
                    src.add_property_annotation(name, JavaAnn('@Id'))
                    src.add_property_annotation(name, JavaAnn('@GeneratedValue'))
                else:
                    raise Exception("id with name " + name + " in class " + cls_name)
                    pass
                column = id_tag.get('column')
                if column is not None and column != name:
                    src.add_property_annotation(name, JavaAnn('@Column', 'name = "' + column + '"'))
                    # type = id_tag.get('type')
                pass

            # plain fields
            for prop in cls.find_all('property', recursive=False):
                name = prop['name']
                index = prop.get('index')
                if index:
                    src.add_property_annotation(name, JavaAnn('@Index', 'name = "' + index + '"'))
                    src.add_import('org.hibernate.annotations.Index')
                lazy = prop.get('lazy')
                if lazy:
                    src.add_property_annotation(name, JavaAnn('@Basic', 'fetch = FetchType.LAZY'))
                col_args = []
                column = prop.get('column')
                classes[cls_name][column] = name
                if column is not None and column != name:
                    col_args.append('name = "' + column + '"')
                length = prop.get('length')
                if length:
                    col_args.append('length = ' + length)
                formula = prop.get('formula')
                if formula:
                    src.add_property_annotation(name, JavaAnn('@Formula', '"' + formula + '"'))
                    src.add_import('org.hibernate.annotations.Formula')
                unique = prop.get('unique')
                if unique:
                    col_args.append('unique = true')
                    # type = prop.get('type')
                if col_args:
                    src.add_property_annotation(name, JavaAnn('@Column', col_args))
                unique_key = prop.get('unique-key')
                if unique_key:
                    unique_args.append(column)
                src.mark_as_mapped(name)
                pass

            # many-to-one entities
            for entity in cls.find_all('many-to-one', recursive=False):
                join_col_args = []
                many_to_one_args = []
                name = entity.get('name')
                lazy = entity.get('lazy')
                fetch = entity.get('fetch')
                target_class = entity.get('class')
                # https://forum.hibernate.org/viewtopic.php?f=1&t=929178&sid=2eb67ddf54a436cbbf601b3adf53fb63
                outer_join = entity.get('outer-join')
                if lazy == 'false' or fetch == 'join':
                    # many-to-one is eager by default, not need to add it explicitly 
                    #many_to_one_args.append('fetch = FetchType.EAGER')
                    pass
                elif lazy is not None or outer_join != 'true':
                    many_to_one_args.append('fetch = FetchType.LAZY')
                cascade = entity.get('cascade')
                if cascade:
                    if cascade == 'all':
                        many_to_one_args.append('cascade = CascadeType.ALL')
                        pass
                    elif cascade == 'merge':
                        many_to_one_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        raise Exception('all-delete-orphan cascade type is not allowed on many-to-one')
                        pass
                    elif cascade == 'delete-orphan':
                        raise Exception('all-delete-orphan cascade type is not allowed on many-to-one')
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')

                # entity_cls = entity.get('class')
                column = entity.get('column')
                if column is not None and column != name + "_id":
                    join_col_args.append('name = "' + column + '"')
                insert = entity.get('insert')
                if insert == 'false':
                    join_col_args.append('insertable = false')
                update = entity.get('update')
                if update == 'false':
                    join_col_args.append('updatable = false')

                if outer_join == 'true':
                    src.add_property_annotation(name, JavaAnn('@Fetch', 'FetchMode.JOIN'))
                    src.add_import('org.hibernate.annotations.Fetch')
                    src.add_import('org.hibernate.annotations.FetchMode')
                elif outer_join:
                    raise Exception('outer-join type ' + outer_join + ' not handled')
                not_found = entity.get('not-found')
                if not_found == 'ignore':
                    src.add_property_annotation(name, JavaAnn('@NotFound', 'action = NotFoundAction.IGNORE'))
                    src.add_import('org.hibernate.annotations.NotFound')
                    src.add_import('org.hibernate.annotations.NotFoundAction')

                unique_key = entity.get('unique-key')
                if unique_key:
                    unique_args.append(column)

                if join_col_args:
                    src.add_property_annotation(name, JavaAnn('@JoinColumn', join_col_args))

                if many_to_one_args:
                    src.add_property_annotation(name, JavaAnn('@ManyToOne', many_to_one_args, target_class))
                else:
                    src.add_property_annotation(name, JavaAnn('@ManyToOne', None, target_class))
                pass

            # one-to-one entities
            for entity in cls.find_all('one-to-one', recursive=False):
                one_to_one_args = []
                name = entity.get('name')
                property_ref = entity.get('property-ref')
                if property_ref:
                    one_to_one_args.append('mappedBy = "' + property_ref + '"')
                cascade = entity.get('cascade')
                # entity_cls = entity.get('class')
                if cascade:
                    if cascade == 'all':
                        one_to_one_args.append('cascade = CascadeType.ALL')
                        pass
                    elif cascade == 'merge':
                        one_to_one_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_one_args.append('cascade = CascadeType.ALL')
                        one_to_one_args.append('orphanRemoval = true')
                        pass
                    elif cascade == 'delete-orphan':
                        one_to_one_args.append('orphanRemoval = true')
                        pass
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')
                if one_to_one_args:
                    src.add_property_annotation(name, JavaAnn('@OneToOne', one_to_one_args))
                else:
                    src.add_property_annotation(name, JavaAnn('@OneToOne'))
                pass

            # list collections
            for collection in cls.find_all('list', recursive=False):
                collection_field(src, collection)
                pass

            # set collections
            for collection in cls.find_all('set', recursive=False):
                collection_field(src, collection)
                pass

            # many-to-many collections
            for collection in cls.find_all('many-to-many', recursive=False):
                collection_field(src, collection, True)
                pass

            # map collections
            for m in cls.find_all('map', recursive=False):
                collection_field(src, m)
                pass

            for component in cls.find_all('component', recursive=False):
                name = component.get('name')
                src.add_property_annotation(name, JavaAnn('@Embedded'))
                attr_override_args = []
                component_attributes = []
                component_attributes += component.find_all('property', recursive=False)
                component_attributes += component.find_all('many-to-one', recursive=False)
                for p in component_attributes:
                    p_name = p['name']
                    p_column = p.get('column')
                    if not p_column:
                        p_column = p_name
                    attr_override_args.append('@AttributeOverride(name = "' + p_name + '", column = @Column(name = "' + p_column + '") )')
                if attr_override_args:
                    src.add_property_annotation(name, JavaAnn('@AttributeOverrides', '{' + ', '.join(attr_override_args) + '}'))

                target_cls = component.get('class')
                if target_cls:
                    target_cls = target_cls.split('.')[-1]
                else:
                    target_cls = src.find_property_type(name)
                if target_cls not in embeddable_classes:
                    embeddable_classes[target_cls] = target_cls
                    target_src = JavaSource(all_class_paths[target_cls])
                    target_src.add_import('javax.persistence.Embeddable')
                    target_src.add_class_annotation('@Embeddable')
                    target_src.write()
                pass

            for comp_id in cls.find_all('composite-id', recursive=False):
                print 'WARN: composite-id found in', cls_name, 'please annotate manually'
                pass

            if unique_args:
                src.add_class_annotation('@Table(name = "' + table + '", uniqueConstraints = { @UniqueConstraint(columnNames = {"' + '", "'.join(unique_args) + '"})})')
            else:
                src.add_class_annotation('@Table(name = "' + table + '")')

            return cls_name, src


def link_peer_fields(sources):
    sources = {}
    for cls_name, src in sources:
        #y = [(prop, ann, annotations) for ann in annotations for prop, annotations in src.prop_annotations if ann.name == '@OneToMany']
        for prop, one_to_many in src.find_scheduled('@OneToMany'):
            target_src = sources[one_to_many.target_class]
            matches = target_src.find_scheduled('@ManyToOne', cls_name)
            if matches:
                if len(matches) == 1:
                    peer_prop, many_to_one = matches[0]

    pass

if __name__ == '__main__':
    java_src_base='../jazva/src/main/java'
    for dp, dn, file_names in os.walk(java_src_base):
        for f in file_names:
            path_split = os.path.splitext(f)
            if path_split[1] == '.java':
                all_class_paths[path_split[0]] = os.path.join(dp, f)

    sources = {}
    for hbm in sys.argv[1:]:
        print '------------ processing', hbm
        cls_name, src = process_hbm(hbm, java_src_base)
        sources[cls_name] = src

    link_peer_fields(sources)
    for src in sources:
        src.write()

