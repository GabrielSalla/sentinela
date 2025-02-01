import inspect
import logging
import re
from types import ModuleType
from typing import Any, Callable, Optional, _TypedDictMeta  # type: ignore[attr-defined]

from data_models.monitor_options import AlertOptions, IssueOptions, MonitorOptions, ReactionOptions
from notifications import BaseNotification

_logger = logging.getLogger("module_check")
_logger.setLevel(logging.INFO)

ERROR_NOT_FUNCTION = "'{display_name}' must be a function"
ERROR_NOT_ASYNC_FUNCTION = "function '{display_name}' must be asynchronous"
ERROR_NOT_SYNC_FUNCTION = "function '{display_name}' must be synchronous"
ERROR_MISSING_FIELD = "'{display_name}' is required"
ERROR_FIELD_WRONG_TYPE = "'{display_name}' must be an instance of '{expected_type}'"
ERROR_OPTIONAL_FIELD_WRONG_TYPE = (
    "'{display_name}' must be an instance of '{expected_type}' or not defined"
)
ERROR_CLASS_NOT_INHERITED = "Class '{display_name}' must be inherited from '{expected_class}'"
ERROR_MISSING_DATACLASS_ATTRIBUTE = (
    "'{display_name}' must have the '{expected_attribute}' field, as specified by '{requirer}'"
)
ERROR_MISSING_FUNCTION = "'{display_name}' function is required"
ERROR_FUNCTION_MUST_HAVE_NO_ARGUMENTS = "'{display_name}' function must have no arguments"
ERROR_FUNCTION_WRONG_ARGUMENTS = "'{display_name}' function must have arguments '{expected_args}'"
ERROR_FUNCTION_WRONG_RETURN_TYPE = "'{display_name}' function must return '{expected_type}'"


def _check_async_function(
    function: Callable[..., Any], display_name: Optional[str] = None
) -> list[str]:
    """Checks if the provided object is a function and if it's async"""
    errors: list[str] = []

    if display_name is None:
        try:
            display_name = function.__name__
        except AttributeError:
            display_name = str(function)

    if not inspect.isfunction(function):
        errors.append(ERROR_NOT_FUNCTION.format(display_name=display_name))
        return errors

    if not inspect.iscoroutinefunction(function):
        errors.append(ERROR_NOT_ASYNC_FUNCTION.format(display_name=display_name))
        return errors

    return errors


def _check_sync_function(
    function: Callable[..., Any], display_name: Optional[str] = None
) -> list[str]:
    """Checks if the provided object is a function and if it's sync"""
    errors: list[str] = []

    if display_name is None:
        try:
            display_name = function.__name__
        except AttributeError:
            display_name = str(function)

    if not inspect.isfunction(function):
        errors.append(ERROR_NOT_FUNCTION.format(display_name=display_name))
        return errors

    if inspect.iscoroutinefunction(function):
        errors.append(ERROR_NOT_SYNC_FUNCTION.format(display_name=display_name))
        return errors

    return errors


def _check_monitor_options(module: ModuleType) -> list[str]:
    """Check if the monitor's 'monitor_options' attribute is defined and if it's a 'MonitorOptions'
    dataclass instance"""
    errors: list[str] = []

    try:
        monitor_options = module.monitor_options
    except AttributeError:
        errors.append(ERROR_MISSING_FIELD.format(display_name="monitor_options"))
        return errors

    if not isinstance(monitor_options, MonitorOptions):
        errors.append(
            ERROR_FIELD_WRONG_TYPE.format(
                display_name="monitor_options", expected_type="MonitorOptions"
            )
        )
        return errors

    return errors


def _check_issue_options(module: ModuleType) -> list[str]:
    """Check if the monitor's 'issue_options' attribute is defined and if it's a 'IssueOptions'
    dataclass instance"""
    errors: list[str] = []

    try:
        issue_options = module.issue_options
    except AttributeError:
        errors.append(ERROR_MISSING_FIELD.format(display_name="issue_options"))
        return errors

    if not isinstance(issue_options, IssueOptions):
        errors.append(
            ERROR_FIELD_WRONG_TYPE.format(
                display_name="issue_options", expected_type="IssueOptions"
            )
        )
        return errors

    return errors


def _check_alert_options(module: ModuleType) -> list[str]:
    """Check if the monitor's 'alert_options' attribute is defined and if it's a 'AlertOptions'
    dataclass instance"""
    errors: list[str] = []

    try:
        alert_options = module.alert_options
    except AttributeError:
        return errors

    if not isinstance(alert_options, AlertOptions):
        errors.append(
            ERROR_OPTIONAL_FIELD_WRONG_TYPE.format(
                display_name="alert_options", expected_type="AlertOptions"
            )
        )
        return errors

    return errors


def _check_reaction_functions(reaction_options: ReactionOptions) -> list[str]:
    """Check if the monitor's 'reaction_options' attribute is configured with lists of async
    functions"""
    errors: list[str] = []

    for field in ReactionOptions.__dataclass_fields__:
        # Check each item in the reactions list
        for item in reaction_options[field]:
            try:
                display_name = f"reaction_options.{field}.{item.__name__}"
            except AttributeError:
                display_name = f"reaction_options.{field}.{str(item)}"

            function_errors = _check_async_function(item, display_name=display_name)
            errors += function_errors

    return errors


def _check_reaction_options(module: ModuleType) -> list[str]:
    """Check if the monitor's 'reaction_options' attribute is defined and if it's a
    'ReactionOptions' dataclass instance"""
    errors: list[str] = []

    try:
        reaction_options = module.reaction_options
    except AttributeError:
        # Allow a monitor to be defined without "reaction_options"
        return errors

    if not isinstance(reaction_options, ReactionOptions):
        errors.append(
            ERROR_OPTIONAL_FIELD_WRONG_TYPE.format(
                display_name="reaction_options", expected_type="ReactionOptions"
            )
        )
        return errors

    return _check_reaction_functions(reaction_options)


def _check_notification_options(module: ModuleType) -> list[str]:
    """Check if the monitor's 'notification_options' attribute is defined and if it's a
    'BaseNotification' dataclass instance"""
    errors: list[str] = []

    try:
        notification_options = module.notification_options
    except AttributeError:
        # Allow a monitor to be defined without "notification_options"
        return errors

    if not isinstance(notification_options, list):
        errors.append(
            ERROR_OPTIONAL_FIELD_WRONG_TYPE.format(
                display_name="notification_options", expected_type="list[Notification]"
            )
        )
        return errors

    for i, notification in enumerate(module.notification_options):
        if not isinstance(notification, BaseNotification):
            errors.append(
                ERROR_FIELD_WRONG_TYPE.format(
                    display_name=f"notification_options[{i}]", expected_type="Notification"
                )
            )
            return errors

    return errors


def _check_issue_data_type(module: ModuleType) -> list[str]:
    """Check if the monitor's 'IssueDataType' attribute is a class inherited from
    'typing.TypedDict' and has the model id key defined in the 'issue_options'"""
    errors: list[str] = []

    try:
        issue_data_type = module.IssueDataType
    except AttributeError:
        errors.append(ERROR_MISSING_FIELD.format(display_name="IssueDataType"))
        return errors

    # This type checking is not ideal, but, currently, it's the only way to do
    if not isinstance(issue_data_type, _TypedDictMeta):
        errors.append(
            ERROR_CLASS_NOT_INHERITED.format(
                display_name="IssueDataType", expected_class="typing.TypedDict"
            )
        )
        return errors

    # The definition of the 'IssueDataType' class will be done in another check function, so just
    # skip the check if it's not defined
    try:
        issue_options = module.issue_options
    except AttributeError:
        return errors

    if issue_options.model_id_key not in issue_data_type.__required_keys__:
        errors.append(
            ERROR_MISSING_DATACLASS_ATTRIBUTE.format(
                display_name="IssueDataType",
                expected_attribute=issue_options.model_id_key,
                requirer="issue_options.model_id_key",
            )
        )
        return errors

    return errors


def _check_search_function(module: ModuleType) -> list[str]:
    """Check if the monitor's 'search' attribute is an async function and has the right signature
    and typing"""
    errors: list[str] = []

    try:
        search_function = module.search
    except AttributeError:
        errors.append(ERROR_MISSING_FUNCTION.format(display_name="search"))
        return errors

    errors += _check_async_function(search_function, display_name="search")
    if len(errors) > 0:
        return errors

    function_args = inspect.getfullargspec(search_function)

    # Check arguments
    if any([function_args.args, function_args.varargs, function_args.varkw]):
        errors.append(ERROR_FUNCTION_MUST_HAVE_NO_ARGUMENTS.format(display_name="search"))
        return errors

    # The definition of the 'IssueDataType' class will be done in another check function, so just
    # skip the check if it's not defined
    try:
        module.IssueDataType
    except AttributeError:
        return errors

    # Check return type
    return_type_str = str(function_args.annotations["return"])
    if not re.match(r"list\[[\w.<>]+.IssueDataType\] \| None", return_type_str):
        errors.append(
            ERROR_FUNCTION_WRONG_RETURN_TYPE.format(
                display_name="search", expected_type="list[IssueDataType] | None"
            )
        )
        return errors

    return errors


def _check_update_function(module: ModuleType) -> list[str]:
    """Check if the monitor's 'update' attribute is an async function and has the right signature
    and typing"""
    errors: list[str] = []

    try:
        update_function = module.update
    except AttributeError:
        errors.append(ERROR_MISSING_FUNCTION.format(display_name="update"))
        return errors

    errors += _check_async_function(update_function, display_name="update")
    if len(errors) > 0:
        return errors

    function_args = inspect.getfullargspec(update_function)

    # Check the 'issues_data' argument
    if "issues_data" not in function_args.args:
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="update", expected_args="issues_data: list[IssueDataType]"
            )
        )
        return errors

    # The definition of the 'IssueDataType' class will be done in another check function, so just
    # skip the check if it's not defined
    try:
        module.IssueDataType
    except AttributeError:
        return errors

    # Check the 'issues_data' argument type
    issues_data_argument_type_str = str(function_args.annotations["issues_data"])
    if not re.match(r"list\[[\w.<>]+.IssueDataType\]", issues_data_argument_type_str):
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="update", expected_args="issues_data: list[IssueDataType]"
            )
        )
        return errors

    # Check there are no other arguments
    if any([function_args.varargs, function_args.varkw]) or function_args.args != ["issues_data"]:
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="update", expected_args="issues_data: list[IssueDataType]"
            )
        )
        return errors

    # Check return type
    return_type_str = str(function_args.annotations["return"])
    if not re.match(r"list\[[\w.<>]+.IssueDataType\] \| None", return_type_str):
        errors.append(
            ERROR_FUNCTION_WRONG_RETURN_TYPE.format(
                display_name="update", expected_type="list[IssueDataType] | None"
            )
        )
        return errors

    return errors


def _check_is_solved_function(module: ModuleType) -> list[str]:
    """Check if the monitor's 'is_solved' attribute is a sync function and has the right signature
    and typing"""
    errors: list[str] = []

    try:
        is_solved_function = module.is_solved
    except AttributeError:
        # The definition of the 'issue_options' instance will be done in another check function, so
        # just skip the check if it's not defined
        try:
            issue_options = module.issue_options
        except AttributeError:
            return errors

        if issue_options.solvable:
            errors.append(ERROR_MISSING_FUNCTION.format(display_name="is_solved"))
            return errors
        return errors

    errors += _check_sync_function(is_solved_function, display_name="is_solved")
    if len(errors) > 0:
        return errors

    function_args = inspect.getfullargspec(is_solved_function)

    # Check the 'issue_data' argument
    if "issue_data" not in function_args.args:
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="is_solved", expected_args="issue_data: IssueDataType"
            )
        )
        return errors

    # The definition of the 'IssueDataType' class will be done in another check function, so just
    # skip the check if it's not defined
    try:
        module.IssueDataType
    except AttributeError:
        return errors

    # Check the 'issue_data' argument type
    issue_data_argument_type_str = str(function_args.annotations["issue_data"])
    if not re.match(r"<class '[\w.<>]+.IssueDataType'>", issue_data_argument_type_str):
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="is_solved", expected_args="issue_data: IssueDataType"
            )
        )
        return errors

    # Check there are no other arguments
    if any([function_args.varargs, function_args.varkw]) or function_args.args != ["issue_data"]:
        errors.append(
            ERROR_FUNCTION_WRONG_ARGUMENTS.format(
                display_name="is_solved", expected_args="issue_data: IssueDataType"
            )
        )
        return errors

    # Check return type
    if function_args.annotations["return"] is not bool:
        errors.append(
            ERROR_FUNCTION_WRONG_RETURN_TYPE.format(display_name="is_solved", expected_type="bool")
        )
        return errors

    return errors


def check_module(module: ModuleType) -> list[str]:
    """Check all the monitor's attributes to prevent problems when executing them, generating
    warnings for every problem detected"""
    errors: list[str] = []

    errors += _check_monitor_options(module)
    errors += _check_issue_options(module)
    errors += _check_alert_options(module)
    errors += _check_reaction_options(module)
    errors += _check_notification_options(module)
    errors += _check_issue_data_type(module)
    errors += _check_search_function(module)
    errors += _check_update_function(module)
    errors += _check_is_solved_function(module)

    return errors
