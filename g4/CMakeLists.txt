cmake_minimum_required(VERSION 3.16)
project(xamsg4 CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Geant4 REQUIRED ui_all vis_all)
find_package(nlohmann_json 3 QUIET)

file(GLOB sources ${PROJECT_SOURCE_DIR}/src/*.cc)
add_executable(xamsg4 xamsg4.cc ${sources})
target_include_directories(xamsg4 PRIVATE ${PROJECT_SOURCE_DIR}/include)
target_link_libraries(xamsg4 PRIVATE ${Geant4_LIBRARIES})
target_compile_definitions(xamsg4 PRIVATE ${Geant4_DEFINITIONS})
target_include_directories(xamsg4 SYSTEM PRIVATE ${Geant4_INCLUDE_DIRS})
if(nlohmann_json_FOUND)
  target_link_libraries(xamsg4 PRIVATE nlohmann_json::nlohmann_json)
endif()

# copy the macros next to the executable
file(GLOB macros ${PROJECT_SOURCE_DIR}/macros/*.mac)
foreach(m ${macros})
  get_filename_component(n ${m} NAME)
  configure_file(${m} ${PROJECT_BINARY_DIR}/${n} COPYONLY)
endforeach()
