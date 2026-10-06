from lectern import agent


def test_agent_definition():
    definition = agent.plist("/Users/someone/.local/bin/lectern")

    assert definition["Label"] == "com.anton.lectern"
    assert definition["ProgramArguments"] == ["/Users/someone/.local/bin/lectern", "serve", "--all"]
    assert definition["RunAtLoad"] is True
    # Restarted after a crash, not after it steps aside for a lectern already running.
    assert definition["KeepAlive"] == {"SuccessfulExit": False}
    assert definition["StandardOutPath"].endswith("Library/Logs/lectern.log")


def test_agent_can_be_kept_to_this_machine():
    arguments = agent.plist("/bin/lectern", host="127.0.0.1")["ProgramArguments"]
    assert arguments[-2:] == ["--host", "127.0.0.1"]


def test_status_reads_the_service_and_not_its_nested_sections():
    printed = """gui/502/com.anton.lectern = {
\tstate = running
\tprogram = /Users/someone/.local/bin/lectern
\tpid = 67191
\tlast exit code = (never exited)
\tendpoints = {
\t\tstate = active
\t}
}"""
    assert agent.describe(printed) == "running (pid 67191)"
    assert agent.describe("\tstate = waiting\n\tlast exit code = 1\n").startswith(
        "loaded, not running (last exit code 1"
    )
