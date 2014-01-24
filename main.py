from bs4 import BeautifulSoup, NavigableString
import re, sys, os, os.path

prop_attrs = {}

def uc_first(s):
    if not s:
        return s
    return s[0].upper() + s[1:]

def lc_first(s):
    if not s:
        return s
    return s[0].lower() + s[1:]

class JavaSource:
    def __init__(self, java_file_path):
        self.java_file_path = java_file_path
        with open(java_file_path) as java_file:
            self.src = java_file.read()
            self.src = self.src.replace('\r', '')

    def add_method_annotation(self, prop, annotation):
        self.src = re.sub(r'^(\n*)(\s*)(public\s+\b\w+\b\s*(?:get|is)' + uc_first(prop) + r'\s*\()', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags = re.MULTILINE)

    def add_class_annotation(self, cls, annotation):
        self.src = re.sub(r'^(\n*)(\s*)(public\s+class\s+' + uc_first(cls) + ')', r'\1\2' + annotation + "\n" + r'\2\3', self.src, 1, flags = re.MULTILINE)

    def add_import(self, imprt):
        self.src = re.sub(r'^(package\s+[\w\.]+;)' + "\n", r'\1' + '\n\nimport ' + imprt + ";\n", self.src, 1, flags = re.MULTILINE)

    def write():
        with open(self.java_file_path, 'w') as java_file:
            java_file.write(self.src)
        

def process_hbm(hbm, java_src_base = '../jazva/src/main/java'):
    with open(hbm) as hbm_file:
        soup = BeautifulSoup(hbm_file, 'xml')
        for cls in soup.findAll('class'):
            cls_name = cls.get('name')
            cls_short_name = cls_name.split('.')[-1]
            table = cls.get('table')
            java_file_path = java_src_base + '/' + cls_name.replace('.', '/') + '.java'
            if not os.path.exists(java_file_path):
                print 'skipping class',cls_name
                continue

            print 'processing class',cls_short_name,'...',
            src = JavaSource(java_file_path)

            src.add_import('javax.persistence.*')
            unique_args = []
            src.add_class_annotation(cls_short_name, '@Entity')

            # primary key
            for id in cls.findAll('id'):
                name = id.get('name')
                if name == 'id':
                    src.add_method_annotation(name, '@Id')
                    src.add_method_annotation(name, '@GeneratedValue')
                else:
                    #TODO
                    pass
                column = id.get('column')
                if column is not None and column != name:
                    src.add_method_annotation(name, '@Column(name = "' + column + '")')
                # type = id.get('type')
                pass

            # plain fields
            for prop in cls.findAll('property'):
                name = prop['name']
                index = prop.get('index')
                if index is not None:
                    src.add_method_annotation(name, '@IndexColumn')
                    src.add_import('org.hibernate.annotations.IndexColumn')
                lazy = prop.get('lazy')
                if lazy is not None:
                    src.add_method_annotation(name, '@Basic(fetch = FetchType.LAZY)')
                col_args = []
                column = prop.get('column')
                if column is not None and column != name:
                    col_args.append('name = "' + column + '"')
                length = prop.get('length')
                if length is not None:
                    col_args.append('length = "' + length + '"')
                formula = prop.get('formula')
                if formula is not None:
                    src.add_method_annotation(name, '@Formula("' + formula + '")')
                    src.add_import('org.hibernate.annotations.Formula')
                unique = prop.get('unique')
                if unique is not None:
                    col_args.append('unique = true')
                # type = prop.get('type')
                if col_args:
                    src.add_method_annotation(name, '@Column(' + ', '.join(col_args) + ')')
                unique_key = entity.get('unique-key')
                if unique_key is not None:
                    unique_args.append(column)
                pass

            # many-to-one entities
            for entity in cls.findAll('many-to-one'):
                # prop_attrs.update(entity.attrs)
                join_col_args = []
                many_to_one_args = []
                name = entity.get('name')
                lazy = entity.get('lazy')
                fetch = entity.get('fetch')
                # https://forum.hibernate.org/viewtopic.php?f=1&t=929178&sid=2eb67ddf54a436cbbf601b3adf53fb63
                outer_join = entity.get('outer-join')
                if lazy == 'false' or fetch == 'join':
                    many_to_one_args.append('fetch = FetchType.EAGER')
                elif lazy is not None or outer_join != 'true':
                    many_to_one_args.append('fetch = FetchType.LAZY')
                cascade = entity.get('cascade')
                if cascade is not None:
                    if cascade == 'all':
                        many_to_one_args.append('cascade = CascadeType.ALL')
                        pass
                    if cascade == 'merge':
                        many_to_one_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        raise Exception('all-delete-orphan cascade type is not allowed on many-to-one')
                        pass
                    elif cascade = 'delete-orphan':
                        raise Exception('all-delete-orphan cascade type is not allowed on many-to-one')
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')

                # entity_cls = entity.get('class')
                column = entity.get('column')
                if column is not None and column != name + "_id":
                    join_col_args.append(name, 'name = "' + column + '"')
                insert = entity.get('insert')
                if insert == 'false':
                    join_col_args.append('insertable = false')
                update = entity.get('update')
                if update == 'false':
                    join_col_args.append('updateable = false')

                if outer_join == 'true':
                    src.add_method_annotation(name, '@Fetch(FetchMode.JOIN)')
                else:
                    raise Exception('outer-join type ' + outer_join + ' not handled')
                not_found = entity.get('not-found')
                if not_found == 'ignore':
                    src.add_method_annotation(name, '@NotFound(action = NotFoundAction.IGNORE)')
                    src.add_import('org.hibernate.annotations.NotFound')
                    src.add_import('org.hibernate.annotations.NotFoundAction')

                unique_key = entity.get('unique-key')
                if unique_key is not None:
                    unique_args.append(column)

                if many_to_one_args:
                    src.add_method_annotation(name, '@ManyToOne(' + ', '.join(many_to_one_args) + ')')
                else:
                    src.add_method_annotation(name, '@ManyToOne')
                pass

            # one-to-one entities
            for entity in cls.findAll('one-to-one'):
                # prop_attrs.update(entity.attrs)
                one_to_one_args = []
                name = entity.get('name')
                property_ref = entity.get('property-ref')
                if property_ref is not None:
                    one_to_one_args.append('mappedBy = "' + property_ref + '"')
                cascade = entity.get('cascade')
                # entity_cls = entity.get('class')
                if cascade is not None:
                    if cascade == 'all':
                        one_to_one_args.append('cascade = CascadeType.ALL')
                        pass
                    if cascade == 'merge':
                        one_to_one_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_one_args.append('cascade = CascadeType.ALL')
                        one_to_one_args.append('orphanRemoval = true')
                        pass
                    elif cascade = 'delete-orphan':
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
            for lst in cls.findAll('list'):
                # prop_attrs.update(lst.attrs)
                name = lst.get('name')
                # lazy = lst.get('lazy')
                # outer_join = lst.get('outer-join')
                table = lst.get('table')
                if table is not None:
                    src.add_method_annotation(name, '@JoinTable(name = "' + table + '")')
                # fetch = lst.get('fetch')
                cascade = lst.get('cascade')
                if cascade is not None:
                    if cascade == 'all':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        pass
                    if cascade == 'merge':
                        one_to_many_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    elif cascade = 'delete-orphan':
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')
                if one_to_one_args:
                    src.add_method_annotation(name, '@OneToOne(' + ', '.join(one_to_one_args) + ')')
                else:
                    src.add_method_annotation(name, '@OneToOne')
                pass

            # set collections
            for collection in cls.findAll('set'):
                # prop_attrs.update(collection.attrs)
                # lazy = collection.get('lazy')
                # inverse = collection.get('inverse')
                # name = collection.get('name')
                # outer_join = collection.get('outer-join')
                # cascade = collection.get('cascade')
                # order_by = collection.get('order-by')
                # table = collection.get('table')
                if cascade is not None:
                    if cascade == 'all':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        pass
                    if cascade == 'merge':
                        one_to_many_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    elif cascade = 'delete-orphan':
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')
                pass

            # map collections
            for m in cls.findAll('map'):
                # prop_attrs.update(m.attrs)
                # cascade = m.get('cascade')
                # inverse = m.get('inverse')
                # name = m.get('name')
                # order_by = m.get('order-by')
                if cascade is not None:
                    if cascade == 'all':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        pass
                    if cascade == 'merge':
                        one_to_many_args.append('cascade = CascadeType.MERGE')
                        pass
                    elif cascade == 'all-delete-orphan':
                        one_to_many_args.append('cascade = CascadeType.ALL')
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    elif cascade = 'delete-orphan':
                        one_to_many_args.append('orphanRemoval = true')
                        pass
                    else:
                        raise Exception('cascade type ' + cascade + ' not handled')
                pass

            for component in cls.findAll('component'):
                # prop_attrs.update(component.attrs)
                # name = collection.get('name')
                # class = collection.get('class')
                pass

            for comp_id in cls.findAll('composite-id'):
                pass

            if unique_args:
                src.add_class_annotation(cls, '@Table(name = "' + table + '", uniqueConstraints = { @UniqueConstraint(columnNames = {"' + '", "'.join(unique_args) + '"})})')
            else:
                src.add_class_annotation(cls, '@Table(name = "' + table + '")')
            src.write()
            print 'done'


if __name__ == '__main__':
    for hbm in sys.argv[1:]:
        process_hbm(hbm)
    #for k in  prop_attrs.keys():
    #    print k,"= collection['" + k + "']"

