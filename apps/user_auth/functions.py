def get_user_label(user, always_show_username=False):
    name = user.get_full_name()
    username = user.username
    if not always_show_username:
        return name.title() or username

    return name and name != username and "%s (%s)" % (name, username) or username
