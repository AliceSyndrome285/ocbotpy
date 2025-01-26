.. role:: raw-html-m2r(raw)
   :format: html


botpy
=====

**botpy** 是基于\ `机器人开放平台API <https://bot.q.qq.com/wiki/develop/api/>`_ 实现的机器人框架，目的提供一个易使用、开发效率高的开发框架。


.. image:: https://img.shields.io/pypi/v/qq-botpy
   :target: https://img.shields.io/pypi/v/qq-botpy
   :alt: PyPI


.. image:: https://api.bkdevops.qq.com/process/api/external/pipelines/projects/qq-guild-open/p-713959939bdc4adca0eea2d4420eef4b/badge?X-DEVOPS-PROJECT-ID=qq-guild-open
   :target: https://devops.woa.com/process/api-html/user/builds/projects/qq-guild-open/pipelines/p-713959939bdc4adca0eea2d4420eef4b/latestFinished?X-DEVOPS-PROJECT-ID=qq-guild-open
   :alt: BK Pipelines Status


准备工作
--------

安装
^^^^

.. code-block:: bash

   pip install qq-botpy

更新包的话需要添加 ``--upgrade`` ``注：需要python3.7+``

使用
^^^^

需要使用的地方\ ``import botpy``

.. code-block:: python

   import botpy

兼容提示
^^^^^^^^

..

   原机器人的老版本\ ``qq-bot``\ 仍然可以使用，但新接口的支持上会逐渐暂停，此次升级不会影响线上使用的机器人


使用方式
--------

快速入门
^^^^^^^^

步骤1
~~~~~

通过继承实现\ ``bot.Client``\ , 实现自己的机器人Client

步骤2
~~~~~

实现机器人相关事件的处理方法,如 ``on_at_message_create``\ ， 详细的事件监听列表，请参考 `事件监听.md <./docs/事件监听.md>`_

如下，是定义机器人被@的后自动回复:

.. code-block:: python

   import botpy
   from botpy.types.message import Message

   class MyClient(botpy.Client):
       async def on_ready(self):
           print(f"robot 「{self.robot.name}」 on_ready!")

       async def on_at_message_create(self, message: Message):
           await message.reply(content=f"机器人{self.robot.name}收到你的@消息了: {message.content}")

``注意:每个事件会下发具体的数据对象，如`message`相关事件是`message.Message`的对象 (部分事件透传了后台数据，暂未实现对象缓存)``

步骤3
~~~~~

设置机器人需要监听的事件通道，并启动\ ``client``

.. code-block:: python

   import botpy
   from botpy.types.message import Message

   class MyClient(botpy.Client):
       async def on_at_message_create(self, message: Message):
           await self.api.post_message(channel_id=message.channel_id, content="content")

   intents = botpy.Intents(public_guild_messages=True)
   client = MyClient(intents=intents)
   client.run(appid="12345", token="xxxx")

备注
^^^^

也可以通过预设置的类型，设置需要监听的事件通道

.. code-block:: python

   import botpy

   intents = botpy.Intents.none()
   intents.public_guild_messages=True

使用API
^^^^^^^

如果要使用\ ``api``\ 方法，可以参考如下方式:

.. code-block:: python

   import botpy
   from botpy.types.message import Message

   class MyClient(botpy.Client):
       async def on_at_message_create(self, message: Message):
           await self.api.post_message(channel_id=message.channel_id, content="content")

更多功能
--------
更多功能请参考: [https://github.com/tencent-connect/botpy]

