import collections
import re
import sys

RX_D = re.compile(r'^\d$')
RX_S = re.compile(r'^\s$')
RX_W = re.compile(r'^\w$')

FIELD_UNICODE_POINT = 0
FIELD_UNICODE_CATEGORY = 2


def load_unicode_data(path):
    unicode_data = []
    with open(path) as f:
        for line in f:
            row = line.rstrip('\r\n').split(';')
            point = row[FIELD_UNICODE_POINT]
            category = row[FIELD_UNICODE_CATEGORY]
            char = chr(int(point, 16))
            unicode_data.append((point, char, category))

    return unicode_data


def regex_tests(unicode_data):
    tests = []
    for point, char, category in unicode_data:
        supercategory = category[0]
        if supercategory == 'P' and RX_W.search(char):
            print('EXCEPTION: point {} char {} category {} \w'.format(point, char, category))
        if supercategory == 'C' and RX_S.search(char):
            print('EXCEPTION: point {} char X category {} \w'.format(point, category))            
        tests.append((point,
                      char,
                      category,
                      supercategory,
                      True if RX_D.search(char) else False,
                      True if RX_S.search(char) else False,
                      True if RX_W.search(char) else False))

    return tests


def get_super_category_to_category(unicode_data):
    retval = collections.defaultdict(set)
    for point, char, category in unicode_data:
        supercategory = category[0]
        retval[supercategory].add(category)

    return retval


def main():
    if len(sys.argv) != 2:
        raise Exception('USAGE {} UNICODE_DATA_PATH'.format(sys.argv[0]))

    unicode_data = load_unicode_data(sys.argv[1])
    super_category_to_category = get_super_category_to_category(unicode_data)
    _regex_tests = regex_tests(unicode_data)
    summary = collections.defaultdict(dict)
    for point, char, category, supercategory, rx_d, rx_s, rx_w in _regex_tests:
        if rx_d:
            if 'd_true' in summary[category]:
                summary[category]['d_true'] += 1
            else:
                summary[category]['d_true'] = 1                
        else:
            if 'd_false' in summary[category]:
                summary[category]['d_false'] += 1
            else:
                summary[category]['d_false'] = 1                

        if rx_d:
            if 'd_true' in summary[supercategory]:
                summary[supercategory]['d_true'] += 1
            else:
                summary[supercategory]['d_true'] = 1                
        else:
            if 'd_false' in summary[supercategory]:
                summary[supercategory]['d_false'] += 1
            else:
                summary[supercategory]['d_false'] = 1                

        if rx_s:
            if 's_true' in summary[category]:
                summary[category]['s_true'] += 1
            else:
                summary[category]['s_true'] = 1                
        else:
            if 's_false' in summary[category]:
                summary[category]['s_false'] += 1
            else:
                summary[category]['s_false'] = 1                

        if rx_s:
            if 's_true' in summary[supercategory]:
                summary[supercategory]['s_true'] += 1
            else:
                summary[supercategory]['s_true'] = 1                
        else:
            if 's_false' in summary[supercategory]:
                summary[supercategory]['s_false'] += 1
            else:
                summary[supercategory]['s_false'] = 1                

        if rx_w:
            if 'w_true' in summary[category]:
                summary[category]['w_true'] += 1
            else:
                summary[category]['w_true'] = 1                
        else:
            if 'w_false' in summary[category]:
                summary[category]['w_false'] += 1
            else:
                summary[category]['w_false'] = 1                

        if rx_w:
            if 'w_true' in summary[supercategory]:
                summary[supercategory]['w_true'] += 1
            else:
                summary[supercategory]['w_true'] = 1                
        else:
            if 'w_false' in summary[supercategory]:
                summary[supercategory]['w_false'] += 1
            else:
                summary[supercategory]['w_false'] = 1                

    for category in sorted(summary.keys()):
        print("{}: \\d: {} \\D: {}\n{}: \\s: {} \\S: {}\n{}: \\w: {} \\W: {}".format(
            category,
            summary[category].get('d_true', 0),
            summary[category].get('d_false', 0),
            category,
            summary[category].get('s_true', 0),
            summary[category].get('s_false', 0),
            category,
            summary[category].get('w_true', 0),
            summary[category].get('w_false', 0)))


main()
