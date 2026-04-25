#pragma once

namespace application {

/**
 * @brief The BekantXApplication class represents the main application for BekantX.
 * @note This class is responsible for initializing and running 
 *          the application, managing the main event loop, and coordinating various components of the application.
 */
class BekantXApplication 
{
    public:
        /**
         * @brief Runs the main application loop for BekantX.
         * @note This method initializes necessary components and enters the main event loop, which should never return.
         */
        void Run();
};

}  // namespace application
