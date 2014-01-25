from bs4 import BeautifulSoup
import re, sys, os

prop_attrs = {}

classes = {}


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
        return inverse_key_column[0:-2]
    raise Exception('Could not determine property name from key column ' + inverse_key_column)


class JavaSource:
    def __init__(self, java_file_path):
        self.java_file_path = java_file_path
        self.cls_short_name = os.path.splitext(os.path.basename(java_file_path))[0]
        with open(java_file_path) as java_file:
            self.src = java_file.read()
            self.src = self.src.replace('\r', '')

    def add_method_annotation(self, prop, annotation):
        if not prop:
            raise Exception('property must not be empty')
        if not annotation:
            raise Exception('annotaion must not be empty')
        self.src = re.sub(r'^(\n*)(\s*)(public\s+\b\w+(?:<\s*\w+\s*>)?\s*(?:get|is)' + uc_first(prop) + r'\s*\()', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags=re.MULTILINE)

    def add_class_annotation(self, annotation):
        self.src = re.sub(r'^(\n*)(\s*)(public\s+class\s+' + self.cls_short_name + ')', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags=re.MULTILINE)

    def add_import(self, imprt):
        self.src = re.sub(r'^(package\s+[\w\.]+;)' + "\n", r'\1' + '\n\nimport ' + imprt + ";\n", self.src, 1, flags=re.MULTILINE)

    def write(self):
        with open(self.java_file_path, 'w') as java_file:
            java_file.write(self.src)


def collection_field(src, collection, many_to_many=False):
    args = []
    join_table_args = []
    name = collection.get('name')
    if not name:
        raise Exception('BAD tag ' + str(collection))
    print '>>>>>>>>>>>>> processing', name
    lazy = collection.get('lazy')
    fetch = collection.get('fetch')
    outer_join = collection.get('outer-join')
    table = collection.get('table')
    if lazy == 'false' or fetch == 'join':
        args.append('fetch = FetchType.EAGER')
    elif lazy is not None or outer_join != 'true':
        args.append('fetch = FetchType.LAZY')

    key_column = None
    key = collection.find('key')
    if key:
        key_column = key.get('column')
        if not key_column:
            kc = key.find('column')
            if kc:
                key_column = kc['name']

    if key_column:
        join_table_args.append('joinColumns = {@JoinColumn(name = "' + key_column + '")}')

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
    if inverse == 'true':
        if not key_column:
            raise Exception('BAD ' + str(key))
        mapped_by_prop = inverse_key_column_to_property(key_column)
        args.append('mappedBy = "' + mapped_by_prop + '"')

    order_by = collection.get('order-by')
    if order_by:
        src.add_method_annotation(name, '@OrderBy("' + order_by + '")')

    if join_table_args:
        src.add_method_annotation(name, '@JoinTable(' + ', '.join(join_table_args) + ')')

    if many_to_many:
        ann = '@OneToMany'
    else:
        ann = '@ManyToMany'

    if args:
        src.add_method_annotation(name, ann + '(' + ', '.join(args) + ')')
    else:
        src.add_method_annotation(name, ann)
    print '<<<<<<<<<<<<<< processed', ann, name


def process_hbm(hbm, java_src_base='../jazva/src/main/java'):
    with open(hbm) as hbm_file:
        soup = BeautifulSoup(hbm_file, 'xml')
        for cls in soup.find('hibernate-mapping').find_all('class', recursive=False):
            cls_name = cls.get('name')
            classes[cls_name] = {}
            cls_short_name = cls_name.split('.')[-1]
            table = cls.get('table')
            java_file_path = java_src_base + '/' + cls_name.replace('.', '/') + '.java'
            if not os.path.exists(java_file_path):
                print 'skipping class', cls_name
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
                    src.add_method_annotation(name, '@Id')
                    src.add_method_annotation(name, '@GeneratedValue')
                else:
                    #TODO
                    pass
                column = id_tag.get('column')
                if column is not None and column != name:
                    src.add_method_annotation(name, '@Column(name = "' + column + '")')
                    # type = id_tag.get('type')
                pass

            # plain fields
            for prop in cls.find_all('property', recursive=False):
                name = prop['name']
                index = prop.get('index')
                if index:
                    src.add_method_annotation(name, '@Index(name = "' + index + '")')
                    src.add_import('org.hibernate.annotations.Index')
                lazy = prop.get('lazy')
                if lazy:
                    src.add_method_annotation(name, '@Basic(fetch = FetchType.LAZY)')
                col_args = []
                column = prop.get('column')
                classes[cls_name][column] = name
                if column is not None and column != name:
                    col_args.append('name = "' + column + '"')
                length = prop.get('length')
                if length:
                    col_args.append('length = "' + length + '"')
                formula = prop.get('formula')
                if formula:
                    src.add_method_annotation(name, '@Formula("' + formula + '")')
                    src.add_import('org.hibernate.annotations.Formula')
                unique = prop.get('unique')
                if unique:
                    col_args.append('unique = true')
                    # type = prop.get('type')
                if col_args:
                    src.add_method_annotation(name, '@Column(' + ', '.join(col_args) + ')')
                unique_key = prop.get('unique-key')
                if unique_key:
                    unique_args.append(column)
                pass

            # many-to-one entities
            for entity in cls.find_all('many-to-one', recursive=False):
                join_col_args = []
                many_to_one_args = []
                name = entity.get('name')
                lazy = entity.get('lazy')
                fetch = entity.get('fetch')
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
                    join_col_args.append('updateable = false')

                if outer_join == 'true':
                    src.add_method_annotation(name, '@Fetch(FetchMode.JOIN)')
                elif outer_join:
                    raise Exception('outer-join type ' + outer_join + ' not handled')
                not_found = entity.get('not-found')
                if not_found == 'ignore':
                    src.add_method_annotation(name, '@NotFound(action = NotFoundAction.IGNORE)')
                    src.add_import('org.hibernate.annotations.NotFound')
                    src.add_import('org.hibernate.annotations.NotFoundAction')

                unique_key = entity.get('unique-key')
                if unique_key:
                    unique_args.append(column)

                if join_col_args:
                    src.add_method_annotation(name, '@JoinColumn(' + ', '.join(join_col_args) + ')')

                if many_to_one_args:
                    src.add_method_annotation(name, '@ManyToOne(' + ', '.join(many_to_one_args) + ')')
                else:
                    src.add_method_annotation(name, '@ManyToOne')
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
                    src.add_method_annotation(name, '@OneToOne(' + ', '.join(one_to_one_args) + ')')
                else:
                    src.add_method_annotation(name, '@OneToOne')
                pass

            # list collections
            for collection in cls.find_all('list', recursive=False):
                print '................ processing list', cls_short_name, collection.get('name')
                collection_field(src, collection)
                pass

            # set collections
            for collection in cls.find_all('set', recursive=False):
                print '................ processing set', cls_short_name, collection.get('name')
                collection_field(src, collection)
                pass

            # many-to-many collections
            for collection in cls.find_all('many-to-many', recursive=False):
                print '................ processing many-to-many', cls_short_name, collection.get('name')
                collection_field(src, collection, True)
                pass

            # map collections
            for m in cls.find_all('map', recursive=False):
                # prop_attrs.update(m.attrs)
                one_to_many_args = []
                cascade = m.get('cascade')
                # inverse = m.get('inverse')
                # name = m.get('name')
                # order_by = m.get('order-by')
                if cascade:
                    if cascade == 'all':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        pass
                    elif cascade == 'merge':
                        one_to_many_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    elif cascade == 'delete-orphan':
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')
                pass

            for component in cls.find_all('component', recursive=False):
                # prop_attrs.update(component.attrs)
                name = component.get('name')
                # class = component.get('class')
                pass

            for comp_id in cls.find_all('composite-id', recursive=False):
                pass

            if unique_args:
                src.add_class_annotation('@Table(name = "' + table + '", uniqueConstraints = { @UniqueConstraint(columnNames = {"' + '", "'.join(unique_args) + '"})})')
            else:
                src.add_class_annotation('@Table(name = "' + table + '")')
            src.write()
            print 'done'


if __name__ == '__main__':
    for hbm in sys.argv[1:]:
        print '------------ processing', hbm
        process_hbm(hbm)
        #for k in  prop_attrs.keys():
        #    print k,"= collection['" + k + "']"

