# Glowtalk

This is an app for generating audiobooks for internet works, chiefly Glowfic. A Glowfic is a collaboratively told story made up of posts, and each post has an author, and it usually has an associated character, which typically indicates kinda the viewpoint that the post is coming from.

This is a small app that will only be used by a few people. It has a web presence, but that's mainly its user interface. It's intended that if you want to run this app, you can download it and run it yourself.

One unusual feature is that we separate out the frontend from the worker daemon. A worker daemon can be pointed at a frontend, which operates a work queue. You and your friends can run the worker daemon on a few of your computers, all pointed at the same frontend in order to generate the audiobook together. This is useful, because a lot of the best audio generation models are kinda slow.

We use sqlite to store data, and alembic for migrations, so any time you make a change to the models, be sure to also create a new alembic migration.

While care is taken for security and privacy, there's lots of ways a clever and malicious person can abuse it. For example, they can fill the work queue with nonsense. Your friends can also do that, but hopefully they'll at least have a good time.

## Main user flow

You land on the home page and paste in the URL to a glowfic. You see any audiobooks that have been generated for that work already, and you can either dive into one of those, fork it, or create a new audiobook for the work.

Then we show you each of the characters in that fic, and a few posts by each, and you get to assign a voice to them. You can also assign a default voice for the work, which will be used if you don't assign a voice to a character. You can also change the voice on a per-post basis, and on a per-snippet-of-text basis too.

While you're doing this, you can ask the server to render a post or a snippet with one voice or another, and you can listen to readings by a voice to help you decide.

Then once you're ready, (or once you get bored fiddling with all of those details), you can start rendering, which fills the work queue with tasks to generate audio one sentence at a time, and the backends start grabbing items off of that queue. As they come in you can start listening, and we display some progress information.

You can re-render any snippet that didn't come out right (we push changes like that, that are short and that have a person waiting for them to the front of the work queue, so that you listen to the new version immediately). We also give you a button to cancel all of the pending work, in case you want to make a major change, like choose a different voice for a character.


