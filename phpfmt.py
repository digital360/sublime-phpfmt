import csv
import os
import os.path
import shutil
import sublime
import sublime_plugin
import subprocess
import time
import sys
import json
import urllib.request
from os.path import dirname, realpath

dist_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, dist_dir)
from diff_match_patch.python3.diff_match_patch import diff_match_patch

def print_debug(*msg):
     if getSetting(sublime.active_window().active_view(), sublime.load_settings('phpfmt.sublime-settings'), "debug", False):
        print(msg)

def getSetting( view, settings, key, default ):
    local = 'phpfmt.' + key
    return view.settings().get( local, settings.get( key, default ) )

def dofmt(eself, eview, sgter = None, src = None, force = False):
    if int(sublime.version()) < 3000:
        print_debug("phpfmt: ST2 not supported")
        return False

    self = eself
    view = eview
    s = sublime.load_settings('phpfmt.sublime-settings')
    additional_extensions = s.get("additional_extensions", [])

    uri = view.file_name()
    dirnm, sfn = os.path.split(uri)
    ext = os.path.splitext(uri)[1][1:]
    if force is False and "php" != ext and not ext in additional_extensions:
        print_debug("phpfmt: not a PHP file")
        return False

    php_bin = getSetting( view, s, "php_bin", "php")
    engine = getSetting(view, s, "engine", "fmt.phar")
    formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", engine)

    if not os.path.isfile(formatter_path):
        sublime.message_dialog("engine file is missing: "+formatter_path)
        return

    if engine != "fmt.phar":
        def localFmt():
            options = getSetting(view, s, "options", [])
            cmd_fmt = [php_bin,formatter_path]+options+[uri]
            print_debug(cmd_fmt)
            p = subprocess.Popen(cmd_fmt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dirnm, shell=False)
            res, err = p.communicate()

            print_debug("p:\n", p.returncode)
            print_debug("out:\n", res.decode('utf-8'))
            print_debug("err:\n", err.decode('utf-8'))
            sublime.set_timeout(revert_active_window, 2000)

        sublime.set_timeout(localFmt, 100)
        return False


    indent_with_space = getSetting( view, s, "indent_with_space", False)
    debug = getSetting( view, s, "debug", False)

    passes = getSetting( view, s, "passes", [])
    excludes = getSetting( view, s, "excludes", [])


    config_file = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "php.tools.ini")

    if force is False and "php" != ext and not ext in additional_extensions:
        print_debug("phpfmt: not a PHP file")
        return False

    if "" != ignore_list:
        if type(ignore_list) is not list:
            ignore_list = ignore_list.split(" ")
        for v in ignore_list:
            pos = uri.find(v)
            if -1 != pos and v != "":
                print_debug("phpfmt: skipping file")
                return False

    if not os.path.isfile(php_bin) and not php_bin == "php":
        print_debug("Can't find PHP binary file at "+php_bin)
        sublime.error_message("Can't find PHP binary file at "+php_bin)

    cmd_ver = [php_bin, '-v'];
    p = subprocess.Popen(cmd_ver, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    res, err = p.communicate()
    print_debug("phpfmt (php_ver) cmd:\n", cmd_ver)
    print_debug("phpfmt (php_ver) out:\n", res.decode('utf-8'))
    print_debug("phpfmt (php_ver) err:\n", err.decode('utf-8'))
    if ('PHP 5.3' in res.decode('utf-8') or 'PHP 5.3' in err.decode('utf-8') or 'PHP 5.4' in res.decode('utf-8') or 'PHP 5.4' in err.decode('utf-8') or 'PHP 5.5' in res.decode('utf-8') or 'PHP 5.5' in err.decode('utf-8') or 'PHP 5.6' in res.decode('utf-8') or 'PHP 5.6' in err.decode('utf-8')):
        s = debugEnvironment(php_bin, formatter_path)
        sublime.message_dialog('Warning.\nPHP 7.0 or newer is required.\nPlease, upgrade your local PHP installation.\nDebug information:'+s)
        return False

    s = debugEnvironment(php_bin, formatter_path)
    print_debug(s)

    lintret = 1
    if "AutoSemicolon" in passes:
        lintret = 0
    else:
        cmd_lint = [php_bin,"-ddisplay_errors=1","-l"];
        if src is None:
            cmd_lint.append(uri)
            p = subprocess.Popen(cmd_lint, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dirnm, shell=False)
        else:
            p = subprocess.Popen(cmd_lint, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            p.stdin.write(src.encode('utf-8'))

        lint_out, lint_err = p.communicate()
        lintret = p.returncode

    if(lintret==0):
        cmd_fmt = [php_bin]

        if not debug:
            cmd_fmt.append("-ddisplay_errors=stderr")

        if psr1:
            cmd_fmt.append("-dshort_open_tag=On")

        cmd_fmt.append(formatter_path)
        cmd_fmt.append("--config="+config_file)

        if indent_with_space is True:
            cmd_fmt.append("--indent_with_space")
        elif indent_with_space > 0:
            cmd_fmt.append("--indent_with_space="+str(indent_with_space))

        if len(passes) > 0:
            cmd_fmt.append("--passes="+','.join(passes))

        if len(excludes) > 0:
            cmd_fmt.append("--exclude="+','.join(excludes))

        if debug:
            cmd_fmt.append("-v")

        if src is None:
            cmd_fmt.append(uri)
        else:
            cmd_fmt.append("-")

        print_debug("cmd_fmt: ", cmd_fmt)

        if src is None:
            p = subprocess.Popen(cmd_fmt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dirnm, shell=False)
        else:
            p = subprocess.Popen(cmd_fmt, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

        if src is not None:
            p.stdin.write(src.encode('utf-8'))

        res, err = p.communicate()

        print_debug("p:\n", p.returncode)
        print_debug("err:\n", err.decode('utf-8'))

        if p.returncode != 0:
            return ''

        return res.decode('utf-8')
    else:
        sublime.status_message("phpfmt: format failed - syntax errors found")
        print_debug("lint error: ", lint_out)

def doreordermethod(eself, eview):
    self = eself
    view = eview
    s = sublime.load_settings('phpfmt.sublime-settings')
    engine = s.get("engine", "fmt.phar")
    if engine != "fmt.phar":
        print_debug("order method not supported in this engine")
        return

    additional_extensions = s.get("additional_extensions", [])
    autoimport = s.get("autoimport", True)
    debug = s.get("debug", False)
    enable_auto_align = s.get("enable_auto_align", False)
    ignore_list = s.get("ignore_list", "")
    indent_with_space = s.get("indent_with_space", False)
    psr1 = s.get("psr1", False)
    psr1_naming = s.get("psr1_naming", psr1)
    psr2 = s.get("psr2", False)
    smart_linebreak_after_curly = s.get("smart_linebreak_after_curly", True)
    visibility_order = s.get("visibility_order", False)
    yoda = s.get("yoda", False)

    passes = s.get("passes", [])

    php_bin = s.get("php_bin", "php")
    formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "fmt.phar")

    config_file = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "php.tools.ini")

    uri = view.file_name()
    dirnm, sfn = os.path.split(uri)
    ext = os.path.splitext(uri)[1][1:]

    if "php" != ext and not ext in additional_extensions:
        print_debug("phpfmt: not a PHP file")
        sublime.status_message("phpfmt: not a PHP file")
        return False

    if not os.path.isfile(php_bin) and not php_bin == "php":
        print_debug("Can't find PHP binary file at "+php_bin)
        sublime.error_message("Can't find PHP binary file at "+php_bin)


    print_debug("phpfmt:", uri)
    if enable_auto_align:
        print_debug("auto align: enabled")
    else:
        print_debug("auto align: disabled")



    cmd_lint = [php_bin,"-l",uri];
    p = subprocess.Popen(cmd_lint, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dirnm, shell=False)
    lint_out, lint_err = p.communicate()

    if(p.returncode==0):
        cmd_fmt = [php_bin]

        if not debug:
            cmd_fmt.append("-ddisplay_errors=stderr")

        cmd_fmt.append(formatter_path)
        cmd_fmt.append("--config="+config_file)

        if psr1:
            cmd_fmt.append("--psr1")

        if psr1_naming:
            cmd_fmt.append("--psr1-naming")

        if psr2:
            cmd_fmt.append("--psr2")

        if indent_with_space:
            cmd_fmt.append("--indent_with_space")
        elif indent_with_space > 0:
            cmd_fmt.append("--indent_with_space="+str(indent_with_space))

        if enable_auto_align:
            cmd_fmt.append("--enable_auto_align")

        if visibility_order:
            cmd_fmt.append("--visibility_order")

        passes.append("OrganizeClass")
        if len(passes) > 0:
            cmd_fmt.append("--passes="+','.join(passes))

        cmd_fmt.append(uri)

        uri_tmp = uri + "~"

        print_debug("cmd_fmt: ", cmd_fmt)

        p = subprocess.Popen(cmd_fmt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=dirnm, shell=False)
        res, err = p.communicate()
        print_debug("err:\n", err.decode('utf-8'))
        sublime.set_timeout(revert_active_window, 50)
    else:
        print_debug("lint error: ", lint_out)

def debugEnvironment(php_bin, formatter_path):
    ret = ""
    cmd_ver = [php_bin,"-v"];
    p = subprocess.Popen(cmd_ver, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    res, err = p.communicate()
    ret += ("phpfmt (php version):\n"+res.decode('utf-8'))
    if err.decode('utf-8'):
        ret += ("phpfmt (php version) err:\n"+err.decode('utf-8'))
    ret += "\n"

    cmd_ver = [php_bin,"-m"];
    p = subprocess.Popen(cmd_ver, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    res, err = p.communicate()
    if res.decode('utf-8').find("tokenizer") != -1:
        ret += ("phpfmt (php tokenizer) found\n")
    else:
        ret += ("phpfmt (php tokenizer):\n"+res.decode('utf-8'))
        if err.decode('utf-8'):
            ret += ("phpfmt (php tokenizer) err:\n"+err.decode('utf-8'))
    ret += "\n"

    cmd_ver = [php_bin,formatter_path,"--version"];
    p = subprocess.Popen(cmd_ver, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    res, err = p.communicate()
    ret += ("phpfmt (fmt.phar version):\n"+res.decode('utf-8'))
    if err.decode('utf-8'):
        ret += ("phpfmt (fmt.phar version) err:\n"+err.decode('utf-8'))
    ret += "\n"

    return ret

def revert_active_window():
    sublime.active_window().active_view().run_command("revert")
    sublime.active_window().active_view().run_command("phpcs_sniff_this_file")

class phpfmt(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        s = sublime.load_settings('phpfmt.sublime-settings')
        format_on_save = s.get("format_on_save", True)

        if format_on_save:
            view.run_command('php_fmt')

class DebugEnvCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        s = sublime.load_settings('phpfmt.sublime-settings')

        php_bin = s.get("php_bin", "php")
        formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "fmt.phar")

        s = debugEnvironment(php_bin, formatter_path)
        sublime.message_dialog(s)

class FmtNowCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        vsize = self.view.size()
        src = self.view.substr(sublime.Region(0, vsize))
        if not src.strip():
            return

        src = dofmt(self, self.view, None, src, True)
        if src is False or src == "":
            return False

        _, err = merge(self.view, vsize, src, edit)
        print_debug(err)

class TogglePassMenuCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        s = sublime.load_settings('phpfmt.sublime-settings')
        engine = s.get("engine", "fmt.phar")
        if engine != "fmt.phar":
            return

        php_bin = s.get("php_bin", "php")
        formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "fmt.phar")

        cmd_passes = [php_bin,formatter_path,'--list-simple'];
        print_debug(cmd_passes)

        p = subprocess.Popen(cmd_passes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

        out, err = p.communicate()

        descriptions = out.decode("utf-8").strip().split(os.linesep)

        def on_done(i):
            if i >= 0 :
                s = sublime.load_settings('phpfmt.sublime-settings')
                passes = s.get('passes', [])
                chosenPass = descriptions[i].split(' ')
                option = chosenPass[0]

                passDesc = option

                if option in passes:
                    passes.remove(option)
                    msg = "phpfmt: "+passDesc+" disabled"
                    print_debug(msg)
                    sublime.status_message(msg)
                else:
                    passes.append(option)
                    msg = "phpfmt: "+passDesc+" enabled"
                    print_debug(msg)
                    sublime.status_message(msg)

                s.set('passes', passes)
                sublime.save_settings('phpfmt.sublime-settings')

        self.view.window().show_quick_panel(descriptions, on_done, sublime.MONOSPACE_FONT)

class ToggleExcludeMenuCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        s = sublime.load_settings('phpfmt.sublime-settings')
        engine = s.get("engine", "fmt.phar")
        if engine != "fmt.phar":
            return

        php_bin = s.get("php_bin", "php")
        formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "fmt.phar")

        cmd_passes = [php_bin,formatter_path,'--list-simple'];
        print_debug(cmd_passes)

        p = subprocess.Popen(cmd_passes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

        out, err = p.communicate()

        descriptions = out.decode("utf-8").strip().split(os.linesep)

        def on_done(i):
            if i >= 0 :
                s = sublime.load_settings('phpfmt.sublime-settings')
                excludes = s.get('excludes', [])
                chosenPass = descriptions[i].split(' ')
                option = chosenPass[0]

                passDesc = option

                if option in excludes:
                    excludes.remove(option)
                    msg = "phpfmt: "+passDesc+" disabled"
                    print_debug(msg)
                    sublime.status_message(msg)
                else:
                    excludes.append(option)
                    msg = "phpfmt: "+passDesc+" enabled"
                    print_debug(msg)
                    sublime.status_message(msg)

                s.set('excludes', excludes)
                sublime.save_settings('phpfmt.sublime-settings')

        self.view.window().show_quick_panel(descriptions, on_done, sublime.MONOSPACE_FONT)

class ToggleCommand(sublime_plugin.TextCommand):
    def run(self, edit, option):
        s = sublime.load_settings('phpfmt.sublime-settings')
        options = {"format_on_save":"format on save"}
        s = sublime.load_settings('phpfmt.sublime-settings')
        value = s.get(option, False)

        if value:
            s.set(option, False)
            msg = "phpfmt: "+options[option]+" disabled"
            print_debug(msg)
            sublime.status_message(msg)
        else:
            s.set(option, True)
            msg = "phpfmt: "+options[option]+" enabled"
            print_debug(msg)
            sublime.status_message(msg)

        sublime.save_settings('phpfmt.sublime-settings')

class UpdatePhpBinCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        def execute(text):
            s = sublime.load_settings('phpfmt.sublime-settings')
            s.set("php_bin", text)

        s = sublime.load_settings('phpfmt.sublime-settings')
        self.view.window().show_input_panel('php binary path:', s.get("php_bin", ""), execute, None, None)

class OrderMethodCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        doreordermethod(self, self.view)

class IndentWithSpacesCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        s = sublime.load_settings('phpfmt.sublime-settings')
        engine = s.get("engine", "fmt.phar")
        if engine != "fmt.phar":
            return

        def setIndentWithSpace(text):
            s = sublime.load_settings('phpfmt.sublime-settings')
            v = text.strip()
            if not v:
                v = False
            else:
                v = int(v)
            s.set("indent_with_space", v)
            sublime.save_settings('phpfmt.sublime-settings')
            sublime.status_message("phpfmt (indentation): done")
            sublime.active_window().active_view().run_command("fmt_now")

        s = sublime.load_settings('phpfmt.sublime-settings')
        spaces = s.get("indent_with_space", 4)
        if not spaces:
            spaces = ""
        spaces = str(spaces)
        self.view.window().show_input_panel('how many spaces? (leave it empty to return to tabs)', spaces, setIndentWithSpace, None, None)

s = sublime.load_settings('phpfmt.sublime-settings')
version = s.get('version', 1)
s.set('version', version)
sublime.save_settings('phpfmt.sublime-settings')

if version == 2:
    print_debug("Convert to version 3")
    s.set('version', 3)
    sublime.save_settings('phpfmt.sublime-settings')

if version == 3:
    print_debug("Convert to version 4")
    s.set('version', 4)
    passes = s.get('passes', [])
    passes.append("ReindentSwitchBlocks")
    s.set('passes', passes)
    sublime.save_settings('phpfmt.sublime-settings')


def selfupdate():
    s = sublime.load_settings('phpfmt.sublime-settings')
    engine = s.get("engine", "fmt.phar")
    if engine != "fmt.phar":
        return

    php_bin = s.get("php_bin", "php")
    formatter_path = os.path.join(dirname(realpath(sublime.packages_path())), "Packages", "phpfmt", "fmt.phar")

    channel = s.get("engine_channel", "lts")
    version = s.get("engine_version", "")

    if version == "":
        releaseJSON = urllib.request.urlopen("https://raw.githubusercontent.com/phpfmt/releases/master/releases.json").read()
        releases = json.loads(releaseJSON.decode('utf-8'))
        version = releases[channel]

    downloadURL = "https://github.com/phpfmt/releases/raw/master/releases/"+channel+"/"+version+"/fmt.phar"
    urllib.request.urlretrieve (downloadURL, formatter_path)

sublime.set_timeout_async(selfupdate, 3000)


class PhpFmtCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        vsize = self.view.size()
        src = self.view.substr(sublime.Region(0, vsize))
        if not src.strip():
            return

        src = dofmt(self, self.view, None, src)
        if src is False or src == "":
            return False

        _, err = merge(self.view, vsize, src, edit)
        print_debug(err)

class MergeException(Exception):
    pass

def _merge(view, size, text, edit):
    def ss(start, end):
        return view.substr(sublime.Region(start, end))
    dmp = diff_match_patch()
    diffs = dmp.diff_main(ss(0, size), text, False)
    dmp.diff_cleanupEfficiency(diffs)
    i = 0
    dirty = False
    for d in diffs:
        k, s = d
        l = len(s)
        if k == 0:
            # match
            l = len(s)
            if ss(i, i+l) != s:
                raise MergeException('mismatch', dirty)
            i += l
        else:
            dirty = True
            if k > 0:
                # insert
                view.insert(edit, i, s)
                i += l
            else:
                # delete
                if ss(i, i+l) != s:
                    raise MergeException('mismatch', dirty)
                view.erase(edit, sublime.Region(i, i+l))
    return dirty

def merge(view, size, text, edit):
    vs = view.settings()
    ttts = vs.get("translate_tabs_to_spaces")
    vs.set("translate_tabs_to_spaces", False)
    origin_src = view.substr(sublime.Region(0, view.size()))
    if not origin_src.strip():
        vs.set("translate_tabs_to_spaces", ttts)
        return (False, '')

    try:
        dirty = False
        err = ''
        if size < 0:
            size = view.size()
        dirty = _merge(view, size, text, edit)
    except MergeException as ex:
        dirty = True
        err = "Could not merge changes into the buffer, edit aborted: %s" % ex[0]
        view.replace(edit, sublime.Region(0, view.size()), origin_src)
    except Exception as ex:
        err = "error: %s" % ex
    finally:
        vs.set("translate_tabs_to_spaces", ttts)
        return (dirty, err)
