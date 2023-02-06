import launch

if not launch.is_installed("litemapy"):
    launch.run_pip("install litemapy", "requirements for MagicPrompt")