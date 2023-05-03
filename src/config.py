import models

feeds: list[models.FeedConfig] = [
    models.FeedConfig(
        name="sshpwauth",
        url="http://danger.rulez.sk/projects/bruteforceblocker/blist.php",
        source="bruteforceblocker",
        disabled=False
    ),
]
