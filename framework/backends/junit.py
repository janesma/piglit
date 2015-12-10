# Copyright (c) 2014, 2015 Intel Corporation

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

""" Module implementing a JUnitBackend for piglit """

from __future__ import print_function, absolute_import
import os.path
import shutil

try:
    from lxml import etree
except ImportError:
    import xml.etree.cElementTree as etree

from framework import grouptools, results, status, exceptions
from framework.core import PIGLIT_CONFIG
from .abstract import FileBackend
from .register import Registry

__all__ = [
    'REGISTRY',
    'JUnitBackend',
]


_JUNIT_SPECIAL_NAMES = ('api', 'search')


def junit_escape(name):
    name = name.replace('.', '_')
    if name in _JUNIT_SPECIAL_NAMES:
        name += '_'
    return name


class JUnitBackend(FileBackend):
    """ Backend that produces ANT JUnit XML

    Based on the following schema:
    https://svn.jenkins-ci.org/trunk/hudson/dtkit/dtkit-format/dtkit-junit-model/src/main/resources/com/thalesgroup/dtkit/junit/model/xsd/junit-7.xsd

    """
    _file_extension = 'xml'

    def __init__(self, dest, junit_suffix='', **options):
        super(JUnitBackend, self).__init__(dest, **options)
        self._test_suffix = junit_suffix

        # make dictionaries of all test names expected to crash/fail
        # for quick lookup when writing results.  Use lower-case to
        # provide case insensitive matches.
        self._expected_failures = {}
        if PIGLIT_CONFIG.has_section("expected-failures"):
            for (fail, _) in PIGLIT_CONFIG.items("expected-failures"):
                self._expected_failures[fail.lower()] = True
        self._expected_crashes = {}
        if PIGLIT_CONFIG.has_section("expected-crashes"):
            for (fail, _) in PIGLIT_CONFIG.items("expected-crashes"):
                self._expected_crashes[fail.lower()] = True

    def initialize(self, metadata):
        """ Do nothing

        Junit doesn't support restore, and doesn't have an initial metadata
        block to write, so all this method does is create the tests directory

        """
        tests = os.path.join(self._dest, 'tests')
        if os.path.exists(tests):
            shutil.rmtree(tests)
        os.mkdir(tests)

    def finalize(self, metadata=None):
        """ Scoop up all of the individual peices and put them together """
        root = etree.Element('testsuites')
        piglit = etree.Element('testsuite', name='piglit')
        root.append(piglit)
        for each in os.listdir(os.path.join(self._dest, 'tests')):
            with open(os.path.join(self._dest, 'tests', each), 'r') as f:
                # parse returns an element tree, and that's not what we want,
                # we want the first (and only) Element node
                # If the element cannot be properly parsed then consider it a
                # failed transaction and ignore it.
                try:
                    piglit.append(etree.parse(f).getroot())
                except etree.ParseError:
                    continue

        # set the test count by counting the number of tests.
        # This must be bytes or unicode
        piglit.attrib['tests'] = str(len(piglit))

        with open(os.path.join(self._dest, 'results.xml'), 'w') as f:
            f.write("<?xml version='1.0' encoding='utf-8'?>\n")
            # lxml has a pretty print we want to use
            if etree.__name__ == 'lxml.etree':
                f.write(etree.tostring(root, pretty_print=True))
            else:
                f.write(etree.tostring(root))

        shutil.rmtree(os.path.join(self._dest, 'tests'))

    def _write(self, f, name, data):
        # Split the name of the test and the group (what junit refers to as
        # classname), and replace piglits '/' separated groups with '.', after
        # replacing any '.' with '_' (so we don't get false groups).
        classname, testname = grouptools.splitname(name)
        classname = classname.split(grouptools.SEPARATOR)
        classname = [junit_escape(e) for e in classname]
        classname = '.'.join(classname)

        # Add the test to the piglit group rather than directly to the root
        # group, this allows piglit junit to be used in conjunction with other
        # piglit
        # TODO: It would be nice if other suites integrating with piglit could
        # set different root names.
        classname = 'piglit.' + classname

        if data.subtests:
            # If there are subtests treat the test as a suite instead of a
            # test, set system-out, system-err, and time on the suite rather
            # than on the testcase
            name='{}.{}'.format(classname, testname)
            element = etree.Element(
                'testsuite',
                name=name,
                time=str(data.time.total))

            out = etree.SubElement(element, 'system-out')
            out.text = data.command + '\n' + data.out
            err = etree.SubElement(element, 'system-err')
            err.text = data.err
            err.text += '\n\nstart time: {}\nend time: {}\n'.format(
                data.time.start, data.time.end)

            for name, result in data.subtests.iteritems():
                sub = self.__make_subcase(name, result, err)
                out = etree.SubElement(sub, 'system-out')
                out.text = 'I am a subtest of {}'.format(name)
                element.append(sub)

            for attrib, xpath in [('failures', './/testcase/failure'),
                                  ('errors', './/testcase/error'),
                                  ('skipped', './/testcase/skipped'),
                                  ('tests', './/testcase')]:
                element.attrib[attrib] = str(len(element.findall(xpath)))

        else:
            element = self.__make_case(testname, classname, data)

        f.write(etree.tostring(element))

    def __make_name(self, testname):
        # Jenkins will display special pages when the test has certain names,
        # so add '_' so the tests don't match those names
        # https://jenkins-ci.org/issue/18062
        # https://jenkins-ci.org/issue/19810
        full_test_name = testname + self._test_suffix
        if full_test_name in _JUNIT_SPECIAL_NAMES:
            testname += '_'
            full_test_name = testname + self._test_suffix
        return full_test_name

    def __make_subcase(self, testname, result, err):
        """Create a <testcase> element for subtests.

        This method is used to create a <testcase> element to nest inside of a
        <testsuite> element when that element represents a test with subtests.
        This differs from __make_case in that it doesn't add as much metadata
        to the <testcase>, since that was attached to the <testsuite> by
        _write, and that it doesn't handle incomplete cases, since subtests
        cannot have incomplete as a status (though that could change).

        """
        full_test_name = self.__make_name(testname)
        element = etree.Element('testcase',
                                name=full_test_name,
                                status=str(result))

        # replace special characters and make case insensitive
        lname = self.__normalize_name(testname)

        expected_result = "pass"

        if lname in self._expected_failures:
            expected_result = "failure"
            # a test can either fail or crash, but not both
            assert lname not in self._expected_crashes

        if lname in self._expected_crashes:
            expected_result = "error"

        self.__add_result(element, result, err, expected_result)

        return element

    def __make_case(self, testname, classname, data):
        """Create a <testcase> element and return it.

        Specifically, this is used to create "normal" test case, one that
        doesn't contain any subtests. __make_subcase is used to create a
        <testcase> which belongs inside a nested <testsuite> node.

        Arguments:
        testname -- the name of the test
        classname -- the name of the group (to use piglit terminology)
        data -- A TestResult instance

        """
        full_test_name = self.__make_name(testname)

        # Create the root element
        element = etree.Element('testcase',
                                name=full_test_name,
                                classname=classname,
                                time=str(data.time.total),
                                status=str(data.result))

        # If this is an incomplete status then none of these values will be
        # available, nor
        if data.result != 'incomplete':
            expected_result = "pass"

            # Add stdout
            out = etree.SubElement(element, 'system-out')
            out.text = data.out

            # Prepend command line to stdout
            out.text = data.command + '\n' + out.text

            # Add stderr
            err = etree.SubElement(element, 'system-err')
            err.text = data.err
            err.text += '\n\nstart time: {}\nend time: {}\n'.format(
                data.time.start, data.time.end)

            element.extend([err, out])

            # replace special characters and make case insensitive
            lname = self.__normalize_name(classname, testname)

            if lname in self._expected_failures:
                expected_result = "failure"
                # a test can either fail or crash, but not both
                assert lname not in self._expected_crashes

            if lname in self._expected_crashes:
                expected_result = "error"

            self.__add_result(element, data.result, err, expected_result)
        else:
            etree.SubElement(element, 'failure', message='Incomplete run.')

        return element

    @staticmethod
    def __normalize_name(testname, classname=None):
        """Nomralize the test name to what is stored in the expected statuses.
        """
        if classname is not None:
            name = (classname + "." + testname).lower()
        else:
            name = testname.lower()
        name = name.replace("=", ".")
        name = name.replace(":", ".")
        return name

    @staticmethod
    def __add_result(element, result, err, expected_result):
        """Add a <skipped>, <failure>, or <error> if necessary."""
        res = None
        # Add relevant result value, if the result is pass then it doesn't
        # need one of these statuses
        if result == 'skip':
            res = etree.SubElement(element, 'skipped')

        elif result in ['fail', 'dmesg-warn', 'dmesg-fail']:
            if expected_result == "failure":
                err.text += "\n\nWARN: passing test as an expected failure"
                res = etree.SubElement(element, 'skipped',
                                       message='expected failure')
            else:
                res = etree.SubElement(element, 'failure')

        elif result == 'crash':
            if expected_result == "error":
                err.text += "\n\nWARN: passing test as an expected crash"
                res = etree.SubElement(element, 'skipped',
                                       message='expected crash')
            else:
                res = etree.SubElement(element, 'error')

        elif expected_result != "pass":
            err.text += "\n\nERROR: This test passed when it "\
                        "expected {0}".format(expected_result)
            res = etree.SubElement(element, 'failure')

        # Add the piglit type to the failure result
        if res is not None:
            res.attrib['type'] = str(result)


def _load(results_file):
    """Load a junit results instance and return a TestrunResult.

    It's worth noting that junit is not as descriptive as piglit's own json
    format, so some data structures will be empty compared to json.

    This tries to not make too many assumptions about the strucuter of the
    JUnit document.

    """
    def populate_result(result, test):
        # This is the fallback path, we'll try to overwrite this with the value
        # in stderr
        result.time = results.TimeAttribute(end=float(test.attrib['time']))
        result.err = test.find('system-err').text

        # The command is prepended to system-out, so we need to separate those
        # into two separate elements
        out = test.find('system-out').text.split('\n')
        result.command = out[0]
        result.out = '\n'.join(out[1:])

        # Try to get the values in stderr for time
        if 'time start' in result.err:
            for line in result.err.split('\n'):
                if line.startswith('time start:'):
                    result.time.start = float(line[len('time start: '):])
                elif line.startswith('time end:'):
                    result.time.end = float(line[len('time end: '):])
                    break

    run_result = results.TestrunResult()

    splitpath = os.path.splitext(results_file)[0].split(os.path.sep)
    if splitpath[-1] != 'results':
        run_result.name = splitpath[-1]
    elif len(splitpath) > 1:
        run_result.name = splitpath[-2]
    else:
        run_result.name = 'junit result'

    tree = etree.parse(results_file).getroot().find('.//testsuite[@name="piglit"]')
    for test in tree.iterfind('testcase'):
        result = results.TestResult()
        # Take the class name minus the 'piglit.' element, replace junit's '.'
        # separator with piglit's separator, and join the group and test names
        name = test.attrib['classname'].split('.', 1)[1]
        name = name.replace('.', grouptools.SEPARATOR)
        name = grouptools.join(name, test.attrib['name'])

        # Remove the trailing _ if they were added (such as to api and search)
        if name.endswith('_'):
            name = name[:-1]

        result.result = test.attrib['status']

        populate_result(result, test)

        run_result.tests[name] = result

    for test in tree.iterfind('testsuite'):
        result = results.TestResult()
        # Take the class name minus the 'piglit.' element, replace junit's '.'
        # separator with piglit's separator, and join the group and test names
        name = test.attrib['name'].split('.', 1)[1]
        name = name.replace('.', grouptools.SEPARATOR)

        # Remove the trailing _ if they were added (such as to api and search)
        if name.endswith('_'):
            name = name[:-1]

        populate_result(result, test)

        for subtest in test.iterfind('testcase'):
            result.subtests[subtest.attrib['name']] = subtest.attrib['status']

        run_result.tests[name] = result

    run_result.calculate_group_totals()

    return run_result


def load(results_dir, compression):  # pylint: disable=unused-argument
    """Searches for a results file and returns a TestrunResult.

    wraps _load and searches for the result file.

    """
    if not os.path.isdir(results_dir):
        return _load(results_dir)
    elif os.path.exists(os.path.join(results_dir, 'tests')):
        raise NotImplementedError('resume support of junit not implemented')
    elif os.path.exists(os.path.join(results_dir, 'results.xml')):
        return _load(os.path.join(results_dir, 'results.xml'))
    else:
        raise exceptions.PiglitFatalError("No results found")


REGISTRY = Registry(
    extensions=['.xml'],
    backend=JUnitBackend,
    load=load,
    meta=lambda x: x,  # The venerable no-op function
)
