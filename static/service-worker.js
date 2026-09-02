/* Timora Service Worker
 *
 * Handles:
 * - Web Push notifications
 * - Notification sound/vibration
 * - Notification clicks
 * - Opening/focusing Timora
 */

self.addEventListener("install", (event) => {
    self.skipWaiting();
});


self.addEventListener("activate", (event) => {
    event.waitUntil(
        self.clients.claim()
    );
});


self.addEventListener("push", (event) => {

    let data = {};

    try {

        data = event.data
            ? event.data.json()
            : {};

    } catch (_) {

        data = {

            title: "🔔 Timora Reminder",

            body: event.data
                ? event.data.text()
                : "Your reminder is due now.",
        };
    }


    const title =
        data.title ||
        "🔔 Timora Reminder";


    const options = {

        body:
            data.body ||
            "Your reminder is due now.",

        icon:
            data.icon ||
            "/static/icons/icon-192.png",

        badge:
            data.badge ||
            "/static/icons/badge-72.png",

        tag:
            data.tag ||
            "timora-reminder",

        requireInteraction:
            data.requireInteraction !== false,

        silent: false,

        renotify: true,

        vibrate: [
            250,
            120,
            250,
            120,
            500,
        ],

        data:
            data.data ||
            {},

        actions:
            data.actions ||
            [
                {
                    action: "done",
                    title: "✅ Done",
                },
                {
                    action: "snooze",
                    title: "⏰ Snooze 10m",
                },
            ],
    };


    event.waitUntil(

        self.registration.showNotification(
            title,
            options
        )

    );
});


self.addEventListener(
    "notificationclick",
    (event) => {

        event.notification.close();


        const action =
            event.action;


        const data =
            event.notification.data ||
            {};


        const reminderId =
            data.reminder_id;


        const url =
            data.url ||
            "/dashboard";


        event.waitUntil(

            (async () => {

                const clients =
                    await self.clients.matchAll(
                        {
                            type: "window",
                            includeUncontrolled: true,
                        }
                    );


                /*
                 * If the user clicked Done,
                 * tell an existing Timora tab.
                 */

                if (
                    action === "done"
                    && reminderId
                ) {

                    for (
                        const client
                        of clients
                    ) {

                        try {

                            await client.focus();

                            await client.postMessage(
                                {
                                    type:
                                        "TIMORA_REMINDER_ACTION",

                                    action:
                                        "done",

                                    reminder_id:
                                        reminderId,
                                }
                            );

                            return;

                        } catch (_) {}
                    }
                }


                /*
                 * Otherwise focus existing Timora.
                 */

                for (
                    const client
                    of clients
                ) {

                    try {

                        await client.focus();

                        return;

                    } catch (_) {}
                }


                /*
                 * No Timora tab exists.
                 * Open dashboard/reminder.
                 */

                if (
                    self.clients.openWindow
                ) {

                    await self.clients.openWindow(
                        url
                    );
                }

            })()

        );
    }
);


self.addEventListener(
    "notificationclose",
    () => {}
);