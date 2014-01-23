from bs4 import BeautifulSoup, NavigableString
import re, sys, os, os.path

prop_attrs = {}

def uc_first(s):
    if not s:
        return s
    return s[0].upper() + s[1:]

def add_method_annotation(src, prop, annotation):
    return re.sub(r'^(\n*)(\s*)(public\s+\b\w+\b\s*(?:get|is)' + uc_first(prop) + r'\s*\()', r'\1\2' + annotation + "\n" + r'\2\3', src, 1, flags = re.MULTILINE)

def add_class_annotation(src, cls, annotation):
    return re.sub(r'^(\n*)(\s*)(public\s+class\s+' + uc_first(cls) + ')', r'\1\2' + annotation + "\n" + r'\2\3', src, 1, flags = re.MULTILINE)

def add_import(src, imprt):
    return re.sub(r'^(package\s+[\w\.]+;)' + "\n", r'\1' + '\n\nimport ' + imprt + ";\n", src, 1, flags = re.MULTILINE)

def process_hbm(hbm, java_src_base = '../src/main/java'):
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

            with open(java_file_path) as java_file:
                src = java_file.read()
            print 'processing class',cls_short_name,'...',

            src = src.replace('\r', '')
            src = add_import(src, 'javax.persistence.*')
            src = add_class_annotation(src, cls_short_name, '@Entity\n@Table(name = "' + table + '")')

            for id in cls.findAll('id'):
                name = id.get('name')
                if name == 'id':
                    src = add_method_annotation(src, name, '@Id')
                    src = add_method_annotation(src, name, '@GeneratedValue')
                else:
                    #TODO
                    pass
                column = id.get('column')
                if column is not None and column != name:
                    src = add_method_annotation(src, name, '@Column(name = "' + column + '")')
                # type = id.get('type')
                pass

            for prop in cls.findAll('property'):
                name = prop['name']
                index = prop.get('index')
                if index is not None:
                    src = add_method_annotation(src, name, '@IndexColumn')
                    src = add_import(src, 'org.hibernate.annotations.IndexColumn')
                #TODO lazy = prop.get('lazy')
                ann = []
                column = prop.get('column')
                if column is not None and column != name:
                    ann.append('name = "' + column + '"')
                length = prop.get('length')
                if length is not None:
                    ann.append('length = "' + length + '"')
                #TODO formula = prop.get('formula')
                unique = prop.get('unique')
                if unique is not None:
                    ann.append('unique = true')
                # type = prop.get('type')
                if ann:
                    src = add_method_annotation(src, name, '@Column(' + ', '.join(ann) + ')')
                pass

            for entity in cls.findAll('many-to-one'):
                # prop_attrs.update(entity.attrs)
                # insert = entity.get('insert')
                # lazy = entity.get('lazy')
                name = entity.get('name')
                src = add_method_annotation(src, name, '@ManyToOne')
                # cascade = entity.get('cascade')
                # column = entity.get('column')
                # outer_join = entity.get('outer-join')
                # unique_key = entity.get('unique-key')
                # update = entity.get('update')
                # not_found = entity.get('not-found')
                # fetch = entity.get('fetch')
                # cls = entity.get('class')
                pass

            for lst in cls.findAll('list'):
                # prop_attrs.update(lst.attrs)
                # lazy = lst.get('lazy')
                # name = lst.get('name')
                # outer_join = lst.get('outer-join')
                # cascade = lst.get('cascade')
                # table = lst.get('table')
                # fetch = lst.get('fetch')
                pass

            for m in cls.findAll('map'):
                # prop_attrs.update(m.attrs)
                # cascade = m.get('cascade')
                # inverse = m.get('inverse')
                # name = m.get('name')
                # order_by = m.get('order-by')
                pass

            for entity in cls.findAll('one-to-one'):
                # prop_attrs.update(entity.attrs)
                # name = entity.get('name')
                # property_ref = entity.get('property-ref')
                # cascade = entity.get('cascade')
                # class = entity.get('class')
                pass

            for collection in cls.findAll('set'):
                # prop_attrs.update(collection.attrs)
                # lazy = collection.get('lazy')
                # inverse = collection.get('inverse')
                # name = collection.get('name')
                # outer_join = collection.get('outer-join')
                # cascade = collection.get('cascade')
                # order_by = collection.get('order-by')
                # table = collection.get('table')
                pass

            for component in cls.findAll('component'):
                # prop_attrs.update(component.attrs)
                # name = collection.get('name')
                # class = collection.get('class')
                pass

            for comp_id in cls.findAll('composite-id'):
                pass

            with open(java_file_path, 'w') as java_file:
                java_file.write(src)
                print 'done'


if __name__ == '__main__':
    for hbm in sys.argv[1:]:
        process_hbm(hbm)
    #for k in  prop_attrs.keys():
    #    print k,"= collection['" + k + "']"

