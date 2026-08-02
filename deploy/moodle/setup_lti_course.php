<?php
/**
 * 在 Moodle 里准备一门带慧眼 LTI 活动的课程（本地联调用）
 *
 * 走 Moodle 自己的 PHP API，而不是点界面或直接改表：
 *   · 点界面：选择器随版本变化，Moodle 5 改了不少表单，脚本极易失效；
 *   · 直接改表：绕过缓存与事件，课程会出现「看得见但点不开」的怪状态。
 *
 * 用法（在容器内）：
 *   php setup_lti_course.php <courseShortname> <studentEmail> <toolTypeId> <caseId>
 */

define('CLI_SCRIPT', true);
require('/opt/bitnami/moodle/config.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/lib/enrollib.php');
require_once($CFG->dirroot . '/lib/moodlelib.php');

// CLI 下没有登录用户（$USER->id = 0），而 add_moduleinfo 会为富文本
// 简介保存草稿文件，那一步要取用户上下文，取到 id=0 就报
// 「Can't find data record in database」—— 错误信息完全指不到这里。
// 显式以管理员身份运行。
\core\session\manager::set_user(get_admin());

[$self, $shortname, $email, $typeid, $caseid] = array_pad($argv, 5, null);
$shortname = $shortname ?: 'FUNDUS-01';
$email     = $email     ?: 'student@huiyan.local';
$typeid    = (int)($typeid ?: 1);
$caseid    = $caseid ?: '89';

$course = $DB->get_record('course', ['shortname' => $shortname]);
if (!$course) {
    fwrite(STDERR, "找不到课程 {$shortname}\n");
    exit(1);
}
$user = $DB->get_record('user', ['email' => $email]);
if (!$user) {
    fwrite(STDERR, "找不到学员 {$email}\n");
    exit(1);
}
echo "课程 {$course->fullname} (id={$course->id})\n";
echo "学员 {$user->firstname}{$user->lastname} (id={$user->id})\n";

// ---- 选课 ----
$studentrole = $DB->get_record('role', ['shortname' => 'student'], '*', MUST_EXIST);
$plugin = enrol_get_plugin('manual');
$manual = null;
foreach (enrol_get_instances($course->id, true) as $inst) {
    if ($inst->enrol === 'manual') { $manual = $inst; break; }
}
if (!$manual) {
    $manual = $DB->get_record('enrol', ['id' => $plugin->add_instance($course)]);
}
$context = context_course::instance($course->id);
if (is_enrolled($context, $user)) {
    echo "选课：已在课程中，跳过\n";
} else {
    $plugin->enrol_user($manual, $user->id, $studentrole->id);
    echo "选课：已加入为学员\n";
}

// ---- 添加外部工具活动 ----
// 幂等：同名活动已存在就不再重复添加，脚本要能反复跑
$name = '眼底判读练习（第一例）';
$exists = $DB->get_record_sql(
    "SELECT l.id FROM {lti} l WHERE l.course = ? AND l.name = ?",
    [$course->id, $name]
);
if ($exists) {
    echo "活动：已存在，跳过（lti id={$exists->id}）\n";
} else {
    echo "[1] 取模块
";
    $module = $DB->get_record('modules', ['name' => 'lti'], '*', MUST_EXIST);
    echo "[2] 模块 id={$module->id}
";

    $info = new stdClass();
    $info->modulename = 'lti';
    $info->module = $module->id;
    $info->course = $course->id;
    // section 0（总览区）在任何课程格式下都存在；
    // 用 1 时若课程还没有第二个小节，add_moduleinfo 会报
    // 「Can't find data record in database」，很难看出是小节的问题
    $info->section = 0;
    $info->visible = 1;
    $info->name = $name;
    $info->typeid = $typeid;
    // 病例号靠自定义参数传给工具；不填则学员落到病例列表
    $info->instructorcustomparameters = "case_id={$caseid}";
    // 4 = 新窗口。iframe 内启动会受第三方 Cookie 拦截影响，
    // 联调时用新窗口更容易看清跳转链路
    $info->launchcontainer = 4;
    $info->introeditor = ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0];
    // 成绩回传需要课程里有对应的成绩项
    $info->grade = 100;
    $info->instructorchoiceacceptgrades = 1;
    $info->instructorchoicesendname = 1;
    $info->instructorchoicesendemailaddr = 1;

    try {
        $created = add_moduleinfo($info, $course);
        echo "活动：已添加（cmid={$created->coursemodule}）\n";
    } catch (Throwable $e) {
        // Moodle 默认只说「找不到数据记录」，不说是哪张表。
        // 不把 debuginfo 打出来，这个错基本没法定位。
        fwrite(STDERR, "活动添加失败：" . get_class($e) . " — " . $e->getMessage() . "\n");
        if (!empty($e->debuginfo)) {
            fwrite(STDERR, "debug: " . $e->debuginfo . "\n");
        }
        fwrite(STDERR, substr($e->getTraceAsString(), 0, 1200) . "\n");
        exit(1);
    }
}

rebuild_course_cache($course->id, true);
echo "完成\n";
