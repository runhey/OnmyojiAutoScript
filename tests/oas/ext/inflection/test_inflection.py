"""
OAS 调用契约，上游不可能知道的断言：
   - script.py 的 run() 靠 camelize(task) 拼出 tasks/<CamelCase>/script_task.py
   - module/config/config_model.py 的 merge_value() 靠 underscore(key) 生成配置项 title
"""
import pathlib
import typing

import pytest

from oas.ext import inflection

_OAS_ROOT = pathlib.Path(__file__).resolve()
for _cand in _OAS_ROOT.parents:
    if ((_cand / 'pyproject.toml').is_file()
            and (_cand / 'oas' / 'ext' / 'inflection' / '__init__.py').is_file()
            and (_cand / 'tasks').is_dir()):
        OAS_ROOT = _cand
        break
else:
    raise RuntimeError('未能从测试文件定位仓库根 (需含 pyproject.toml / oas/ext/inflection/ / tasks/)')

TestParameters = typing.Tuple[typing.Tuple[str, str], ...]

SINGULAR_TO_PLURAL: TestParameters = (
    ("search", "searches"),
    ("switch", "switches"),
    ("fix", "fixes"),
    ("box", "boxes"),
    ("process", "processes"),
    ("address", "addresses"),
    ("case", "cases"),
    ("stack", "stacks"),
    ("wish", "wishes"),
    ("fish", "fish"),
    ("jeans", "jeans"),
    ("funky jeans", "funky jeans"),

    ("category", "categories"),
    ("query", "queries"),
    ("ability", "abilities"),
    ("agency", "agencies"),
    ("movie", "movies"),

    ("archive", "archives"),

    ("index", "indices"),

    ("wife", "wives"),
    ("safe", "saves"),
    ("half", "halves"),

    ("move", "moves"),

    ("salesperson", "salespeople"),
    ("person", "people"),

    ("spokesman", "spokesmen"),
    ("man", "men"),
    ("woman", "women"),

    ("basis", "bases"),
    ("diagnosis", "diagnoses"),
    ("diagnosis_a", "diagnosis_as"),

    ("datum", "data"),
    ("medium", "media"),
    ("stadium", "stadia"),
    ("analysis", "analyses"),

    ("node_child", "node_children"),
    ("child", "children"),

    ("experience", "experiences"),
    ("day", "days"),

    ("comment", "comments"),
    ("foobar", "foobars"),
    ("newsletter", "newsletters"),

    ("old_news", "old_news"),
    ("news", "news"),

    ("series", "series"),
    ("species", "species"),

    ("quiz", "quizzes"),

    ("perspective", "perspectives"),

    ("ox", "oxen"),
    ("passerby", "passersby"),
    ("photo", "photos"),
    ("buffalo", "buffaloes"),
    ("tomato", "tomatoes"),
    ("potato", "potatoes"),
    ("dwarf", "dwarves"),
    ("elf", "elves"),
    ("information", "information"),
    ("equipment", "equipment"),
    ("bus", "buses"),
    ("status", "statuses"),
    ("status_code", "status_codes"),
    ("mouse", "mice"),

    ("louse", "lice"),
    ("house", "houses"),
    ("octopus", "octopi"),
    ("virus", "viri"),
    ("alias", "aliases"),
    ("portfolio", "portfolios"),

    ("vertex", "vertices"),
    ("matrix", "matrices"),
    ("matrix_fu", "matrix_fus"),

    ("axis", "axes"),
    ("testis", "testes"),
    ("crisis", "crises"),

    ("rice", "rice"),
    ("shoe", "shoes"),

    ("horse", "horses"),
    ("prize", "prizes"),
    ("edge", "edges"),

    ("cow", "kine"),
    ("database", "databases"),
    ("human", "humans")
)

CAMEL_TO_UNDERSCORE: TestParameters = (
    ("Product",               "product"),
    ("SpecialGuest",          "special_guest"),
    ("ApplicationController", "application_controller"),
    ("Area51Controller",      "area51_controller"),
)

CAMEL_TO_UNDERSCORE_WITHOUT_REVERSE: TestParameters = (
    ("HTMLTidy",              "html_tidy"),
    ("HTMLTidyGenerator",     "html_tidy_generator"),
    ("FreeBSD",               "free_bsd"),
    ("HTML",                  "html"),
)

STRING_TO_PARAMETERIZED: TestParameters = (
    ("Donald E. Knuth", "donald-e-knuth"),
    (
        "Random text with *(bad)* characters",
        "random-text-with-bad-characters"
    ),
    ("Allow_Under_Scores", "allow_under_scores"),
    ("Trailing bad characters!@#", "trailing-bad-characters"),
    ("!@#Leading bad characters", "leading-bad-characters"),
    ("Squeeze   separators", "squeeze-separators"),
    ("Test with + sign", "test-with-sign"),
    ("Test with malformed utf8 \251", "test-with-malformed-utf8"),
)

STRING_TO_PARAMETERIZE_WITH_NO_SEPARATOR: TestParameters = (
    ("Donald E. Knuth", "donaldeknuth"),
    ("With-some-dashes", "with-some-dashes"),
    ("Random text with *(bad)* characters", "randomtextwithbadcharacters"),
    ("Trailing bad characters!@#", "trailingbadcharacters"),
    ("!@#Leading bad characters", "leadingbadcharacters"),
    ("Squeeze   separators", "squeezeseparators"),
    ("Test with + sign", "testwithsign"),
    ("Test with malformed utf8 \251", "testwithmalformedutf8"),
)

STRING_TO_PARAMETERIZE_WITH_UNDERSCORE: TestParameters = (
    ("Donald E. Knuth", "donald_e_knuth"),
    (
        "Random text with *(bad)* characters",
        "random_text_with_bad_characters"
    ),
    ("With-some-dashes", "with-some-dashes"),
    ("Retain_underscore", "retain_underscore"),
    ("Trailing bad characters!@#", "trailing_bad_characters"),
    ("!@#Leading bad characters", "leading_bad_characters"),
    ("Squeeze   separators", "squeeze_separators"),
    ("Test with + sign", "test_with_sign"),
    ("Test with malformed utf8 \251", "test_with_malformed_utf8"),
)

STRING_TO_PARAMETERIZED_AND_NORMALIZED: TestParameters = (
    ("Malmö", "malmo"),
    ("Garçons", "garcons"),
    ("Ops\331", "opsu"),
    ("Ærøskøbing", "rskbing"),
    ("Aßlar", "alar"),
    ("Japanese: 日本語", "japanese"),
)

UNDERSCORE_TO_HUMAN: TestParameters = (
    ("employee_salary",       "Employee salary"),
    ("employee_id",           "Employee"),
    ("underground",           "Underground"),
)

MIXTURE_TO_TITLEIZED: TestParameters = (
    ('active_record',         'Active Record'),
    ('ActiveRecord',          'Active Record'),
    ('action web service',    'Action Web Service'),
    ('Action Web Service',    'Action Web Service'),
    ('Action web service',    'Action Web Service'),
    ('actionwebservice',      'Actionwebservice'),
    ('Actionwebservice',      'Actionwebservice'),
    ("david's code",          "David's Code"),
    ("David's code",          "David's Code"),
    ("david's Code",          "David's Code"),
    ("ana índia",             "Ana Índia"),
    ("Ana Índia",             "Ana Índia"),
)


ORDINAL_NUMBERS: TestParameters = (
    ("-1", "-1st"),
    ("-2", "-2nd"),
    ("-3", "-3rd"),
    ("-4", "-4th"),
    ("-5", "-5th"),
    ("-6", "-6th"),
    ("-7", "-7th"),
    ("-8", "-8th"),
    ("-9", "-9th"),
    ("-10", "-10th"),
    ("-11", "-11th"),
    ("-12", "-12th"),
    ("-13", "-13th"),
    ("-14", "-14th"),
    ("-20", "-20th"),
    ("-21", "-21st"),
    ("-22", "-22nd"),
    ("-23", "-23rd"),
    ("-24", "-24th"),
    ("-100", "-100th"),
    ("-101", "-101st"),
    ("-102", "-102nd"),
    ("-103", "-103rd"),
    ("-104", "-104th"),
    ("-110", "-110th"),
    ("-111", "-111th"),
    ("-112", "-112th"),
    ("-113", "-113th"),
    ("-1000", "-1000th"),
    ("-1001", "-1001st"),
    ("0", "0th"),
    ("1", "1st"),
    ("2", "2nd"),
    ("3", "3rd"),
    ("4", "4th"),
    ("5", "5th"),
    ("6", "6th"),
    ("7", "7th"),
    ("8", "8th"),
    ("9", "9th"),
    ("10", "10th"),
    ("11", "11th"),
    ("12", "12th"),
    ("13", "13th"),
    ("14", "14th"),
    ("20", "20th"),
    ("21", "21st"),
    ("22", "22nd"),
    ("23", "23rd"),
    ("24", "24th"),
    ("100", "100th"),
    ("101", "101st"),
    ("102", "102nd"),
    ("103", "103rd"),
    ("104", "104th"),
    ("110", "110th"),
    # 同上，上游原为 "111st"
    ("111", "111th"),
    ("112", "112th"),
    ("113", "113th"),
    ("1000", "1000th"),
    ("1001", "1001st"),
)

UNDERSCORES_TO_DASHES: TestParameters = (
    ("street",                "street"),
    ("street_address",        "street-address"),
    ("person_street_address", "person-street-address"),
)

STRING_TO_TABLEIZE: TestParameters = (
    ("person", "people"),
    ("Country", "countries"),
    ("ChildToy", "child_toys"),
    ("_RecipeIngredient", "_recipe_ingredients"),
)


def test_pluralize_plurals() -> None:
    assert "plurals" == inflection.pluralize("plurals")
    assert "Plurals" == inflection.pluralize("Plurals")


def test_pluralize_empty_string() -> None:
    assert "" == inflection.pluralize("")


@pytest.mark.parametrize(
    ("word", ),
    [(word,) for word in inflection.UNCOUNTABLES]
)
def test_uncountability(word: str) -> None:
    assert word == inflection.singularize(word)
    assert word == inflection.pluralize(word)
    assert inflection.pluralize(word) == inflection.singularize(word)


def test_uncountable_word_is_not_greedy() -> None:
    uncountable_word = "ors"
    countable_word = "sponsor"

    inflection.UNCOUNTABLES.add(uncountable_word)
    try:
        assert uncountable_word == inflection.singularize(uncountable_word)
        assert uncountable_word == inflection.pluralize(uncountable_word)
        assert (
            inflection.pluralize(uncountable_word) ==
            inflection.singularize(uncountable_word)
        )

        assert "sponsor" == inflection.singularize(countable_word)
        assert "sponsors" == inflection.pluralize(countable_word)
        assert (
            "sponsor" ==
            inflection.singularize(inflection.pluralize(countable_word))
        )
    finally:
        inflection.UNCOUNTABLES.remove(uncountable_word)


@pytest.mark.parametrize(("singular", "plural"), SINGULAR_TO_PLURAL)
def test_pluralize_singular(singular: str, plural: str) -> None:
    assert plural == inflection.pluralize(singular)
    assert plural.capitalize() == inflection.pluralize(singular.capitalize())


@pytest.mark.parametrize(("singular", "plural"), SINGULAR_TO_PLURAL)
def test_singularize_plural(singular: str, plural: str) -> None:
    assert singular == inflection.singularize(plural)
    assert singular.capitalize() == inflection.singularize(plural.capitalize())


@pytest.mark.parametrize(("singular", "plural"), SINGULAR_TO_PLURAL)
def test_pluralize_plural(singular: str, plural: str) -> None:
    assert plural == inflection.pluralize(plural)
    assert plural.capitalize() == inflection.pluralize(plural.capitalize())


@pytest.mark.parametrize(("before", "titleized"), MIXTURE_TO_TITLEIZED)
def test_titleize(before: str, titleized: str) -> None:
    assert titleized == inflection.titleize(before)


@pytest.mark.parametrize(("camel", "underscore"), CAMEL_TO_UNDERSCORE)
def test_camelize(camel: str, underscore: str) -> None:
    assert camel == inflection.camelize(underscore)


def test_camelize_with_lower_downcases_the_first_letter() -> None:
    assert 'capital' == inflection.camelize('Capital', False)


def test_camelize_with_underscores() -> None:
    assert "CamelCase" == inflection.camelize('Camel_Case')


@pytest.mark.parametrize(
    ("camel", "underscore"),
    CAMEL_TO_UNDERSCORE + CAMEL_TO_UNDERSCORE_WITHOUT_REVERSE
)
def test_underscore(camel: str, underscore: str) -> None:
    assert underscore == inflection.underscore(camel)


@pytest.mark.parametrize(
    ("some_string", "parameterized_string"),
    STRING_TO_PARAMETERIZED
)
def test_parameterize(some_string: str, parameterized_string: str) -> None:
    assert parameterized_string == inflection.parameterize(some_string)


@pytest.mark.parametrize(
    ("some_string", "parameterized_string"),
    STRING_TO_PARAMETERIZED_AND_NORMALIZED
)
def test_parameterize_and_normalize(some_string: str, parameterized_string: str) -> None:
    assert parameterized_string == inflection.parameterize(some_string)


@pytest.mark.parametrize(
    ("some_string", "parameterized_string"),
    STRING_TO_PARAMETERIZE_WITH_UNDERSCORE
)
def test_parameterize_with_custom_separator(some_string: str, parameterized_string: str) -> None:
    assert parameterized_string == inflection.parameterize(some_string, '_')


@pytest.mark.parametrize(
    ("some_string", "parameterized_string"),
    STRING_TO_PARAMETERIZED
)
def test_parameterize_with_multi_character_separator(
    some_string: str,
    parameterized_string: str
) -> None:
    assert (
        parameterized_string.replace('-', '__sep__') ==
        inflection.parameterize(some_string, '__sep__')
    )


@pytest.mark.parametrize(
    ("some_string", "parameterized_string"),
    STRING_TO_PARAMETERIZE_WITH_NO_SEPARATOR
)
def test_parameterize_with_no_separator(some_string: str, parameterized_string: str) -> None:
    assert parameterized_string == inflection.parameterize(some_string, '')


@pytest.mark.parametrize(("underscore", "human"), UNDERSCORE_TO_HUMAN)
def test_humanize(underscore: str, human: str) -> None:
    assert human == inflection.humanize(underscore)


@pytest.mark.parametrize(("number", "ordinalized"), ORDINAL_NUMBERS)
def test_ordinal(number: str, ordinalized: str) -> None:
    assert ordinalized == number + inflection.ordinal(int(number))


@pytest.mark.parametrize(("number", "ordinalized"), ORDINAL_NUMBERS)
def test_ordinalize(number: str, ordinalized: str) -> None:
    assert ordinalized == inflection.ordinalize(int(number))


@pytest.mark.parametrize(("input", "expected"), UNDERSCORES_TO_DASHES)
def test_dasherize(input: str, expected: str) -> None:
    assert inflection.dasherize(input) == expected


@pytest.mark.parametrize(("string", "tableized"), STRING_TO_TABLEIZE)
def test_tableize(string: str, tableized: str) -> None:
    assert inflection.tableize(string) == tableized


def test_transliterate() -> None:
    assert inflection.transliterate('älämölö') == 'alamolo'
    assert inflection.transliterate('Ærøskøbing') == 'rskbing'


def test_empty_inputs() -> None:
    assert inflection.camelize('') == ''
    assert inflection.underscore('') == ''
    assert inflection.singularize('') == ''
    assert inflection.dasherize('') == ''


class TestOasCallSites:
    """
    注意 OAS 并不使用 pluralize/singularize/tableize 等（英文单复数对一个阴阳师
    脚本没有意义），但它们随整库一起 vendored 进来，所以保留上游完整套件。
    """

    def test_camelize_task_names_to_real_task_dirs(self) -> None:
        tasks_dir = OAS_ROOT / 'tasks'
        names = sorted(p.name for p in tasks_dir.iterdir() if p.is_dir())
        assert names, 'tasks/ 为空，断言失去意义'

        for name in names:
            if name.startswith('__') or name.endswith('__'):
                # __pycache__ 由导入副作用生成，不是任务目录，且不满足往返约束
                continue
            assert inflection.camelize(inflection.underscore(name)) == name, (
                f'{name}: camelize(underscore(name)) 往返不一致，'
                f'得到 {inflection.camelize(inflection.underscore(name))!r}'
            )

    @pytest.mark.parametrize('raw, expect', [
        ('goto_main', 'GotoMain'),
        ('guild_activity_monitor', 'GuildActivityMonitor'),
        ('daily_trifles', 'DailyTrifles'),
        ('hyakkiyakou', 'Hyakkiyakou'),
        ('kekkai_utilize', 'KekkaiUtilize'),
        ('auto_checkin_big_god', 'AutoCheckinBigGod'),
    ])
    def test_camelize_suso_scheduler_task_names(self, raw: str, expect: str) -> None:
        assert inflection.camelize(raw) == expect
        assert (OAS_ROOT / 'tasks' / expect).is_dir()

    @pytest.mark.parametrize('raw, expect', [
        # tasks/GuildActivityMonitor/config.py 的真实字段名
        ('Dokan', 'dokan'),
        ('AbyssShadows', 'abyss_shadows'),
        ('GuildBanquet', 'guild_banquet'),
        ('DemonRetreat', 'demon_retreat'),
        # tasks/AbyssShadows/config.py
        ('CombatTime_enable', 'combat_time_enable'),
    ])
    def test_underscore_config_field_names(self, raw: str, expect: str) -> None:
        """
        config_model.py 的 merge_value()：

            item["title"] = value["title"] if "title" in value else inflection.underscore(key)
        """
        assert inflection.underscore(raw) == expect

    def test_camelize_underscore_not_strictly_inverse(self) -> None:
        assert inflection.underscore('IOError') == 'io_error'
        assert inflection.camelize(inflection.underscore('IOError')) == 'IoError'


class TestVendoredModuleIntegrity:
    """vendored 副本自身的完整性"""

    def test_license_bundled(self) -> None:
        # MIT 要求搬运时保留版权声明与许可声明
        license_file = OAS_ROOT / 'oas' / 'ext' / 'inflection' / 'LICENSE'
        assert license_file.is_file()
        text = license_file.read_text(encoding='utf-8')
        assert 'Janne Vanhala' in text
        assert 'Permission is hereby granted' in text

    def test_public_api_complete(self) -> None:
        for name in ('camelize', 'dasherize', 'humanize', 'ordinal', 'ordinalize',
                     'parameterize', 'pluralize', 'singularize', 'tableize',
                     'titleize', 'transliterate', 'underscore'):
            assert callable(getattr(inflection, name)), name

    def test_irregular_rules_registered(self) -> None:
        """模块末尾 8 次 _irregular() 调用应已把不规则词并入规则表"""
        assert len(inflection.PLURALS) > 0
        assert len(inflection.SINGULARS) > 0
        assert inflection.pluralize('person') == 'people'
        assert inflection.singularize('kine') == 'cow'

    def test_singularize_shadowed_loop_variable(self) -> None:
        """
        singularize() 用 `inflection` 当循环变量，遮蔽了模块名本身。
        函数内局部变量、无副作用，但 vendored 副本刻意保留以便与上游 diff。
        """
        assert inflection.singularize('octopi') == 'octopus'
        assert inflection.__name__.endswith('inflection')
