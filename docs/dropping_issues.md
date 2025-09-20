# Dropping issues
In some cases, a monitor may encounter edge cases where certain issues cannot be resolved automatically. While these edge cases should be considered during monitor development, dropping issues manually can serve as a solution for unavoidable situations.

Issues can be dropped either via an [HTTP request](./http_server.md) or a [Slack message](./slack_commands.md).

> [!IMPORTANT]
> Since dropping issues is intended only for specific scenarios, issues IDs should be manually retrieved by querying the Sentinela application database.

# Example scenario requiring issue dropping
Consider a monitor that checks for inconsistencies in user registration information. If an issue is created for a specific user who is later deleted from the database, the monitor may be unable to resolve this issue automatically as there won't be updated information for the user.

Unless the monitor handles the case of missing information and creates the updated data for the issue to a value that will result in it being considered as solved, the issue will need to be manually dropped.

The preferred approach for handling unresolved issues is to implement logic within the monitor’s `update` function.

# Dealing with edge cases in the `update` function
Since all active issues are passed as argument to `update`, the function can check for cases where the information for the issue can no longer be obtained and include a "updated issue data" in the return list. By doing this, the issue will be updated with the provided data and resolved automatically, removing the need for manual intervention.

```python
async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    user_ids = [user["id"] for user in issues_data]
    users = await get_users_data(user_ids)

    missing_users_ids = set(user_ids) - {user["id"] for user in users}
    for missing_user_id in missing_users_ids:
        users.append({
            "id": missing_user_id,
            "name": "deleted_user",
        })

    return users

def is_solved(issue_data: IssueDataType) -> bool:
    return issue_data["name"] is not None
```

**Explanation**
- **User data retrieval**: The `update` function first retrieves the issues ids from `issues_data` and then fetches data for these users with `get_users_data`.
- **Missing user detection**: By comparing the IDs from `issues_data` with those in the retrieved `users` list, the function identifies any users that no longer exist.
- **Force update**: For each missing user, an entry with `name: "deleted_user"` is appended to `users`. This "updated issue data" ensures the issue can be considered as resolved.
- **Automatic resolution**: The `is_solved` function checks if `issue_data["name"]` is not empty. Issues for deleted users are automatically considered resolved based on this logic.

This approach lets the monitor handle edge cases seamlessly, removing the need to drop issues manually.
